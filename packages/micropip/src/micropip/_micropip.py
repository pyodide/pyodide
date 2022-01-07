import asyncio
import copy
import functools
import hashlib
import importlib
import io
import json
import tempfile
from importlib.metadata import version as get_version

from packaging.requirements import Requirement
from packaging.version import Version
from packaging.markers import default_environment

from pathlib import Path
from typing import Dict, Any, Union, List, Tuple, Optional
from zipfile import ZipFile

from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel
from .package import PackageDict, PackageMetadata

from pyodide import IN_BROWSER, to_js

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
    BUILTIN_PACKAGES = pyodide_js._module.packages.to_py()
else:
    BUILTIN_PACKAGES = {}

if IN_BROWSER:
    from pyodide_js import loadedPackages
else:

    class loadedPackages:  # type: ignore
        @staticmethod
        def to_py():
            return {}


if IN_BROWSER:
    from pyodide.http import pyfetch

    async def fetch_bytes(url: str, **kwargs) -> bytes:
        return await (await pyfetch(url, **kwargs)).bytes()

    async def fetch_string(url: str, **kwargs) -> str:
        return await (await pyfetch(url, **kwargs)).string()

else:
    from urllib.request import urlopen, Request

    async def fetch_bytes(url: str, **kwargs) -> bytes:
        return urlopen(Request(url, headers=kwargs)).read()

    async def fetch_string(url: str, **kwargs) -> str:
        return (await fetch_bytes(url, **kwargs)).decode()


if IN_BROWSER:
    from asyncio import gather
else:
    # asyncio.gather will schedule any coroutines to run on the event loop but
    # we want to avoid using the event loop at all. Instead just run the
    # coroutines in sequence.
    # TODO: Use an asyncio testing framework to avoid this
    async def gather(*coroutines):  # type: ignore
        result = []
        for coroutine in coroutines:
            result.append(await coroutine)
        return result


async def _get_pypi_json(pkgname):
    url = f"https://pypi.org/pypi/{pkgname}/json"
    return json.loads(await fetch_string(url))


def _is_pure_python_wheel(filename: str):
    return filename.endswith("py3-none-any.whl")


def _parse_wheel_url(url: str) -> Tuple[str, Dict[str, Any], str]:
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
    wheel = {
        "digests": None,  # checksums not available
        "filename": file_name,
        "packagetype": "bdist_wheel",
        "python_version": python_tag,
        "abi_tag": abi_tag,
        "platform": platform,
        "url": url,
    }

    return name, wheel, version


def _extract_wheel(fd):
    with ZipFile(fd) as zf:
        zf.extractall(WHEEL_BASE)


def _validate_wheel(data, fileinfo):
    if fileinfo.get("digests") is None:
        # No checksums available, e.g. because installing
        # from a different location than PyPI.
        return
    sha256 = fileinfo["digests"]["sha256"]
    m = hashlib.sha256()
    m.update(data.getvalue())
    if m.hexdigest() != sha256:
        raise ValueError("Contents don't match hash")


async def _install_wheel(name, fileinfo):
    url = fileinfo["url"]
    wheel = io.BytesIO(fileinfo["wheel_bytes"])
    _validate_wheel(wheel, fileinfo)
    _extract_wheel(wheel)
    setattr(loadedPackages, name, url)


class _PackageManager:
    def __init__(self):
        self.installed_packages = PackageDict()

    async def gather_requirements(
        self,
        requirements: Union[str, List[str]],
        ctx=None,
        keep_going: bool = False,
    ):
        ctx = ctx or default_environment()
        ctx.setdefault("extra", None)
        if isinstance(requirements, str):
            requirements = [requirements]

        transaction: Dict[str, Any] = {
            "wheels": [],
            "pyodide_packages": [],
            "locked": copy.deepcopy(self.installed_packages),
            "failed": [],
            "keep_going": keep_going,
        }
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(
                self.add_requirement(requirement, ctx, transaction)
            )

        await gather(*requirement_promises)
        return transaction

    async def install(
        self, requirements: Union[str, List[str]], ctx=None, keep_going: bool = False
    ):
        async def _install(install_func, done_callback):
            await install_func
            done_callback()

        transaction = await self.gather_requirements(requirements, ctx, keep_going)

        if transaction["failed"]:
            failed_requirements = ", ".join(
                [f"'{req}'" for req in transaction["failed"]]
            )
            raise ValueError(
                f"Couldn't find a pure Python 3 wheel for: {failed_requirements}"
            )

        wheel_promises = []
        # Install built-in packages
        pyodide_packages = transaction["pyodide_packages"]
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
                        {pkg.name: pkg for pkg in pyodide_packages},
                    ),
                )
            )

        # Now install PyPI packages
        for name, wheel, ver in transaction["wheels"]:
            # detect whether the wheel metadata is from PyPI or from custom location
            # wheel metadata from PyPI has SHA256 checksum digest.
            wheel_source = "pypi" if wheel["digests"] is not None else wheel["url"]
            wheel_promises.append(
                _install(
                    _install_wheel(name, wheel),
                    functools.partial(
                        self.installed_packages.update,
                        {name: PackageMetadata(name, str(ver), wheel_source)},
                    ),
                )
            )

        await gather(*wheel_promises)

    async def add_requirement(
        self, requirement: Union[str, Requirement], ctx, transaction
    ):
        """Add a requirement to the transaction.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        if isinstance(requirement, Requirement):
            req = requirement
        elif requirement.endswith(".whl"):
            # custom download location
            name, wheel, version = _parse_wheel_url(requirement)
            name = name.lower()
            if not _is_pure_python_wheel(wheel["filename"]):
                raise ValueError(f"'{wheel['filename']}' is not a pure Python 3 wheel")

            await self.add_wheel(name, wheel, version, (), ctx, transaction)
            return
        else:
            req = Requirement(requirement)
        req.name = req.name.lower()

        # If there's a Pyodide package that matches the version constraint, use
        # the Pyodide package instead of the one on PyPI
        if (
            req.name in BUILTIN_PACKAGES
            and BUILTIN_PACKAGES[req.name]["version"] in req.specifier
        ):
            version = BUILTIN_PACKAGES[req.name]["version"]
            transaction["pyodide_packages"].append(
                PackageMetadata(name=req.name, version=version, source="pyodide")
            )
            return

        if req.marker:
            # handle environment markers
            # https://www.python.org/dev/peps/pep-0508/#environment-markers
            if not req.marker.evaluate(ctx):
                return

        # Is some version of this package is already installed?
        if req.name in transaction["locked"]:
            ver = transaction["locked"][req.name].version
            if ver in req.specifier:
                # installed version matches, nothing to do
                return
            else:
                raise ValueError(
                    f"Requested '{requirement}', "
                    f"but {req.name}=={ver} is already installed"
                )
        metadata = await _get_pypi_json(req.name)
        wheel, ver = self.find_wheel(metadata, req)
        if wheel is None and ver is None:
            if transaction["keep_going"]:
                transaction["failed"].append(req)
            else:
                raise ValueError(
                    f"Couldn't find a pure Python 3 wheel for '{req}'. "
                    "You can use `micropip.install(..., keep_going=True)` to get a list of all packages with missing wheels."
                )
        else:
            await self.add_wheel(req.name, wheel, ver, req.extras, ctx, transaction)

    async def add_wheel(self, name, wheel, version, extras, ctx, transaction):
        transaction["locked"][name] = PackageMetadata(name=name, version=version)
        wheel_bytes = await fetch_bytes(wheel["url"])
        wheel["wheel_bytes"] = wheel_bytes

        with ZipFile(io.BytesIO(wheel_bytes)) as zip_file:  # type: ignore
            dist = pkg_resources_distribution_for_wheel(zip_file, name, "???")
        for recurs_req in dist.requires(extras):
            await self.add_requirement(recurs_req, ctx, transaction)

        transaction["wheels"].append((name, wheel, version))

    def find_wheel(
        self, metadata: Dict[str, Any], req: Requirement
    ) -> Tuple[Any, Optional[Version]]:
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
            (Version(v) for v in req.specifier.filter(releases)),  # type: ignore
            reverse=True,
        )
        for ver in candidate_versions:
            release = releases[str(ver)]
            for fileinfo in release:
                if _is_pure_python_wheel(fileinfo["filename"]):
                    return fileinfo, ver

        return None, None


# Make PACKAGE_MANAGER singleton
PACKAGE_MANAGER = _PackageManager()
del _PackageManager


def install(requirements: Union[str, List[str]], keep_going: bool = False):
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

    Returns
    -------
    ``Future``

        A ``Future`` that resolves to ``None`` when all packages have been
        downloaded and installed.
    """
    importlib.invalidate_caches()
    return asyncio.ensure_future(
        PACKAGE_MANAGER.install(requirements, keep_going=keep_going)
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
