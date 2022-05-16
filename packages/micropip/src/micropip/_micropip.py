import asyncio
import copy
import functools
import hashlib
import importlib
import io
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from pyodide import IN_BROWSER, to_js

from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel
from .package import PackageDict, PackageMetadata

# Provide stubs for testing in native python
if IN_BROWSER:
    import pyodide_js

if IN_BROWSER:
    # Random note: getsitepackages is not available in a virtual environment...
    # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
    # problem is not fixed)
    from site import getsitepackages

    WHEEL_BASE = Path(getsitepackages()[0])
else:
    WHEEL_BASE = Path(tempfile.mkdtemp())

if IN_BROWSER:
    BUILTIN_PACKAGES = pyodide_js._api.packages.to_py()
else:
    BUILTIN_PACKAGES = {}

if IN_BROWSER:
    from pyodide_js import loadedPackages
else:

    class loadedPackages:  # type: ignore[no-redef]
        @staticmethod
        def to_py():
            return {}


if IN_BROWSER:
    from pyodide.http import pyfetch

    async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
        return await (await pyfetch(url, **kwargs)).bytes()

    async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
        return await (await pyfetch(url, **kwargs)).string()

else:
    from urllib.request import Request, urlopen

    async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
        return urlopen(Request(url, headers=kwargs)).read()

    async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
        return (await fetch_bytes(url, kwargs)).decode()


if IN_BROWSER:
    from asyncio import gather
else:
    # asyncio.gather will schedule any coroutines to run on the event loop but
    # we want to avoid using the event loop at all. Instead just run the
    # coroutines in sequence.
    # TODO: Use an asyncio testing framework to avoid this
    async def gather(*coroutines):  # type: ignore[no-redef]
        result = []
        for coroutine in coroutines:
            result.append(await coroutine)
        return result


async def _get_pypi_json(pkgname: str, fetch_extra_kwargs: dict[str, str]):
    url = f"https://pypi.org/pypi/{pkgname}/json"
    return json.loads(await fetch_string(url, fetch_extra_kwargs))


def _is_pure_python_wheel(filename: str):
    return filename.endswith("py3-none-any.whl")


@dataclass
class WheelInfo:
    name: str
    version: Version
    filename: str
    packagetype: str
    python_version: str
    abi_tag: str
    platform: str
    url: str
    project_name: str | None = None
    digests: dict[str, str] | None = None
    wheel_bytes: bytes | None = None


@dataclass
class Transaction:
    wheels: list[WheelInfo]
    pyodide_packages: list[PackageMetadata]
    locked: PackageDict
    failed: list[Requirement]
    keep_going: bool
    deps: bool
    pre: bool


def _parse_wheel_url(url: str) -> WheelInfo:
    """Parse wheels URL and extract available metadata

    See https://www.python.org/dev/peps/pep-0427/#file-name-convention
    """
    file_name = Path(url).name
    # also strip '.whl' extension.
    wheel_name = Path(url).stem
    tokens = wheel_name.split("-")
    # TODO: support optional build tags in the filename (cf PEP 427)
    if len(tokens) < 5:
        raise ValueError(f"{file_name} is not a valid wheel file name.")
    version, python_tag, abi_tag, platform = tokens[-4:]
    name = "-".join(tokens[:-4])
    return WheelInfo(
        name=name,
        version=Version(version),
        filename=file_name,
        packagetype="bdist_wheel",
        python_version=python_tag,
        abi_tag=abi_tag,
        platform=platform,
        url=url,
    )


def _extract_wheel(fd: io.BytesIO):
    with ZipFile(fd) as zf:
        zf.extractall(WHEEL_BASE)


def _validate_wheel(data: io.BytesIO, wheelinfo: WheelInfo):
    if wheelinfo.digests is None:
        # No checksums available, e.g. because installing
        # from a different location than PyPI.
        return
    sha256 = wheelinfo.digests["sha256"]
    m = hashlib.sha256()
    m.update(data.getvalue())
    if m.hexdigest() != sha256:
        raise ValueError("Contents don't match hash")


async def _install_wheel(wheelinfo: WheelInfo):
    url = wheelinfo.url
    if not wheelinfo.wheel_bytes:
        raise RuntimeError(
            "Micropip internal error: attempted to install wheel before downloading it?"
        )
    wheel = io.BytesIO(wheelinfo.wheel_bytes)
    _validate_wheel(wheel, wheelinfo)
    _extract_wheel(wheel)
    name = wheelinfo.project_name
    assert name
    setattr(loadedPackages, name, url)


class _PackageManager:
    def __init__(self):
        self.installed_packages = PackageDict()

    async def gather_requirements(
        self,
        requirements: list[str],
        ctx: dict[str, str],
        keep_going: bool,
        deps: bool,
        pre: bool,
        fetch_extra_kwargs: dict[str, str],
    ) -> Transaction:

        transaction = Transaction(
            wheels=[],
            pyodide_packages=[],
            locked=copy.deepcopy(self.installed_packages),
            failed=[],
            keep_going=keep_going,
            deps=deps,
            pre=pre,
        )
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(
                self.add_requirement(requirement, ctx, transaction, fetch_extra_kwargs)
            )

        await gather(*requirement_promises)
        return transaction

    async def install(
        self,
        requirements: list[str],
        ctx: dict[str, str],
        keep_going: bool,
        deps: bool,
        credentials: str | None,
        pre: bool,
    ):
        async def _install(install_func, done_callback):
            await install_func
            done_callback()

        fetch_extra_kwargs = dict()

        if credentials:
            fetch_extra_kwargs["credentials"] = credentials
        transaction = await self.gather_requirements(
            requirements, ctx, keep_going, deps, pre, fetch_extra_kwargs
        )

        if transaction.failed:
            failed_requirements = ", ".join([f"'{req}'" for req in transaction.failed])
            raise ValueError(
                f"Couldn't find a pure Python 3 wheel for: {failed_requirements}"
            )

        wheel_promises = []
        # Install built-in packages
        pyodide_packages = transaction.pyodide_packages
        if len(pyodide_packages):
            # Note: branch never happens in out-of-browser testing because in
            # that case BUILTIN_PACKAGES is empty.
            wheel_promises.append(
                _install(
                    asyncio.ensure_future(
                        pyodide_js.loadPackage(
                            to_js([name for [name, _, _] in pyodide_packages])
                        )
                    ),
                    functools.partial(
                        self.installed_packages.update,
                        {canonicalize_name(pkg.name): pkg for pkg in pyodide_packages},
                    ),
                )
            )

        # Now install PyPI packages
        for wheel in transaction.wheels:
            # detect whether the wheel metadata is from PyPI or from custom location
            # wheel metadata from PyPI has SHA256 checksum digest.
            wheel_source = "pypi" if wheel.digests is not None else wheel.url
            name = wheel.project_name
            assert name
            wheel_promises.append(
                _install(
                    _install_wheel(wheel),
                    functools.partial(
                        self.installed_packages.update,
                        {
                            canonicalize_name(name): PackageMetadata(
                                name, str(wheel.version), wheel_source
                            )
                        },
                    ),
                )
            )

        await gather(*wheel_promises)

    async def add_requirement(
        self,
        requirement: str | Requirement,
        ctx: dict[str, str],
        transaction: Transaction,
        fetch_extra_kwargs: dict[str, str],
    ):
        """Add a requirement to the transaction.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        if isinstance(requirement, Requirement):
            req = requirement
        elif requirement.endswith(".whl"):
            # custom download location
            wheel = _parse_wheel_url(requirement)
            if not _is_pure_python_wheel(wheel.filename):
                raise ValueError(f"'{wheel.filename}' is not a pure Python 3 wheel")

            await self.add_wheel(wheel, set(), ctx, transaction, fetch_extra_kwargs)
            return
        else:
            req = Requirement(requirement)

        if transaction.pre:
            req.specifier.prereleases = True

        req.name = canonicalize_name(req.name)

        # If there's a Pyodide package that matches the version constraint, use
        # the Pyodide package instead of the one on PyPI
        if req.name in BUILTIN_PACKAGES and req.specifier.contains(
            BUILTIN_PACKAGES[req.name]["version"], prereleases=True
        ):
            version = BUILTIN_PACKAGES[req.name]["version"]
            transaction.pyodide_packages.append(
                PackageMetadata(name=req.name, version=str(version), source="pyodide")
            )
            return

        if req.marker:
            # handle environment markers
            # https://www.python.org/dev/peps/pep-0508/#environment-markers
            if not req.marker.evaluate(ctx):
                return

        # Is some version of this package is already installed?
        if req.name in transaction.locked:
            ver = transaction.locked[req.name].version
            if req.specifier.contains(ver, prereleases=True):
                # installed version matches, nothing to do
                return
            else:
                raise ValueError(
                    f"Requested '{requirement}', "
                    f"but {req.name}=={ver} is already installed"
                )
        metadata = await _get_pypi_json(req.name, fetch_extra_kwargs)

        try:
            wheel = self.find_wheel(metadata, req)
        except ValueError:
            transaction.failed.append(req)
            if not transaction.keep_going:
                raise
        else:
            await self.add_wheel(
                wheel,
                req.extras,
                ctx,
                transaction,
                fetch_extra_kwargs,
            )

    async def add_wheel(
        self,
        wheel: WheelInfo,
        extras: set[str],
        ctx: dict[str, str],
        transaction: Transaction,
        fetch_extra_kwargs: dict[str, str],
    ):
        normalized_name = canonicalize_name(wheel.name)
        transaction.locked[normalized_name] = PackageMetadata(
            name=wheel.name,
            version=str(wheel.version),
        )

        try:
            wheel_bytes = await fetch_bytes(wheel.url, fetch_extra_kwargs)
        except Exception as e:
            if wheel.url.startswith("https://files.pythonhosted.org/"):
                raise e
            else:
                raise ValueError(
                    f"Couldn't fetch wheel from '{wheel.url}'."
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS)."
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

        wheel.wheel_bytes = wheel_bytes

        with ZipFile(io.BytesIO(wheel_bytes)) as zip_file:
            dist = pkg_resources_distribution_for_wheel(zip_file, wheel.name, "???")

        wheel.project_name = dist.project_name
        if wheel.project_name == "UNKNOWN":
            wheel.project_name = wheel.name

        if transaction.deps:
            for recurs_req in dist.requires(extras):
                await self.add_requirement(
                    recurs_req, ctx, transaction, fetch_extra_kwargs
                )

        transaction.wheels.append(wheel)

    def find_wheel(self, metadata: dict[str, Any], req: Requirement) -> WheelInfo:
        """Parse metadata to find the latest version of pure python wheel.

        Parameters
        ----------
        metadata : ``Dict[str, Any]``

            Package search result from PyPI,
            See: https://warehouse.pypa.io/api-reference/json.html

        Returns
        -------
        fileinfo : Dict[str, Any] or None
            The metadata of the Python wheel, or None if there is no pure Python wheel.
        ver : Version or None
            The version of the Python wheel, or None if there is no pure Python wheel.
        """
        releases = metadata.get("releases", {})
        candidate_versions = sorted(
            (Version(v) for v in req.specifier.filter(releases)),
            reverse=True,
        )
        for ver in candidate_versions:
            release = releases[str(ver)]
            for fileinfo in release:
                if _is_pure_python_wheel(fileinfo["filename"]):
                    wheel = _parse_wheel_url(fileinfo["url"])
                    wheel.digests = fileinfo["digests"]
                    return wheel

        raise ValueError(
            f"Couldn't find a pure Python 3 wheel for '{req}'. "
            "You can use `micropip.install(..., keep_going=True)` to get a list of all packages with missing wheels."
        )


# Make PACKAGE_MANAGER singleton
PACKAGE_MANAGER = _PackageManager()
del _PackageManager


def install(
    requirements: str | list[str],
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
):
    """Install the given package and all of its dependencies.

    See :ref:`loading packages <loading_packages>` for more information.

    This only works for packages that are either pure Python or for packages
    with C extensions that are built in Pyodide. If a pure Python package is not
    found in the Pyodide repository it will be loaded from PyPI.

    When used in web browsers, downloads from PyPI will be cached. When run in
    Node.js, packages are currently not cached, and will be re-downloaded each
    time ``micropip.install`` is run.

    Parameters
    ----------
    requirements : ``str | List[str]``

        A requirement or list of requirements to install. Each requirement is a
        string, which should be either a package name or URL to a wheel:

        - If the requirement ends in ``.whl`` it will be interpreted as a URL.
          The file must be a wheel named in compliance with the
          `PEP 427 naming convention <https://www.python.org/dev/peps/pep-0427/#file-format>`_.

        - If the requirement does not end in ``.whl``, it will interpreted as the
          name of a package. A package by this name must either be present in the
          Pyodide repository at `indexURL <globalThis.loadPyodide>` or on PyPI

    keep_going : ``bool``, default: False

        This parameter decides the behavior of the micropip when it encounters a
        Python package without a pure Python wheel while doing dependency
        resolution:

        - If ``False``, an error will be raised on first package with a missing wheel.

        - If ``True``, the micropip will keep going after the first error, and report a list
          of errors at the end.

    deps : ``bool``, default: True

        If ``True``, install dependencies specified in METADATA file for
        each package. Otherwise do not install dependencies.

    credentials : ``Optional[str]``

        This parameter specifies the value of ``credentials`` when calling the
        `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__ function
        which is used to download the package.

        When not specified, ``fetch()`` is called without ``credentials``.

    pre : ``bool``, default: False

        If ``True``, include pre-release and development versions.
        By default, micropip only finds stable versions.

    Returns
    -------
    ``Future``

        A ``Future`` that resolves to ``None`` when all packages have been
        downloaded and installed.
    """
    importlib.invalidate_caches()
    ctx = default_environment()
    ctx.setdefault("extra", "")
    if isinstance(requirements, str):
        requirements = [requirements]

    return asyncio.ensure_future(
        PACKAGE_MANAGER.install(
            requirements,
            ctx=ctx,
            keep_going=keep_going,
            deps=deps,
            credentials=credentials,
            pre=pre,
        )
    )


def _list():
    """Get the dictionary of installed packages.

    Returns
    -------
    packages : :any:`micropip.package.PackageDict`
        A dictionary of installed packages.

        >>> import micropip
        >>> await micropip.install('regex') # doctest: +SKIP
        >>> package_list = micropip.list()
        >>> print(package_list) # doctest: +SKIP
        Name              | Version  | Source
        ----------------- | -------- | -------
        regex             | 2021.7.6 | pyodide
        >>> "regex" in package_list # doctest: +SKIP
        True
    """
    packages = copy.deepcopy(PACKAGE_MANAGER.installed_packages)

    # Add packages that are loaded through pyodide.loadPackage
    for name, pkg_source in loadedPackages.to_py().items():
        if name in packages:
            continue

        version = BUILTIN_PACKAGES[name]["version"]
        source = "pyodide"
        if pkg_source != "default channel":
            # Pyodide package loaded from a custom URL
            source = pkg_source
        packages[name] = PackageMetadata(name=name, version=version, source=source)
    return packages


if __name__ == "__main__":
    install("snowballstemmer")
