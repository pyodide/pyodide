import asyncio
import hashlib
import importlib
import json
from asyncio import gather
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import distributions as importlib_distributions
from importlib.metadata import version as importlib_version
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import Tag, sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from pyodide import to_js
from pyodide._package_loader import get_dynlibs, wheel_dist_info_dir

from ._compat import (
    REPODATA_PACKAGES,
    fetch_bytes,
    fetch_string,
    loadDynlib,
    loadedPackages,
    loadPackage,
)
from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel
from .package import PackageDict, PackageMetadata


async def _get_pypi_json(pkgname: str, fetch_kwargs: dict[str, str]) -> Any:
    url = f"https://pypi.org/pypi/{pkgname}/json"
    try:
        metadata = await fetch_string(url, fetch_kwargs)
    except OSError as e:
        raise ValueError(
            f"Can't fetch metadata for '{pkgname}' from PyPI. "
            "Please make sure you have entered a correct package name."
        ) from e
    return json.loads(metadata)


@dataclass
class WheelInfo:
    name: str
    version: Version
    filename: str
    build: tuple[int, str] | tuple[()]
    tags: frozenset[Tag]
    url: str
    project_name: str | None = None
    digests: dict[str, str] | None = None
    data: BytesIO | None = None
    _dist: Any = None
    dist_info: Path | None = None
    _requires: list[Requirement] | None = None

    @staticmethod
    def from_url(url: str) -> "WheelInfo":
        """Parse wheels URL and extract available metadata

        See https://www.python.org/dev/peps/pep-0427/#file-name-convention
        """
        file_name = Path(url).name
        name, version, build, tags = parse_wheel_filename(file_name)
        return WheelInfo(
            name=name,
            version=version,
            filename=file_name,
            build=build,
            tags=tags,
            url=url,
        )

    def is_compatible(self):
        if self.filename.endswith("py3-none-any.whl"):
            return True
        for tag in sys_tags():
            if tag in self.tags:
                return True
        return False

    async def download(self, fetch_kwargs):
        try:
            wheel_bytes = await fetch_bytes(self.url, fetch_kwargs)
        except OSError as e:
            if self.url.startswith("https://files.pythonhosted.org/"):
                raise e
            else:
                raise ValueError(
                    f"Can't fetch wheel from '{self.url}'."
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS)."
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

        self.data = BytesIO(wheel_bytes)

        with ZipFile(self.data) as zip_file:
            self._dist = pkg_resources_distribution_for_wheel(
                zip_file, self.name, "???"
            )

        self.project_name = self._dist.project_name
        if self.project_name == "UNKNOWN":
            self.project_name = self.name

    def validate(self):
        if self.digests is None:
            # No checksums available, e.g. because installing
            # from a different location than PyPI.
            return
        sha256 = self.digests["sha256"]
        m = hashlib.sha256()
        assert self.data
        m.update(self.data.getvalue())
        if m.hexdigest() != sha256:
            raise ValueError("Contents don't match hash")

    def extract(self, target: Path) -> None:
        assert self.data
        with ZipFile(self.data) as zf:
            zf.extractall(target)
        dist_info_name: str = wheel_dist_info_dir(ZipFile(self.data), self.name)
        self.dist_info = target / dist_info_name

    def requires(self, extras: set[str]) -> list[str]:
        if not self._dist:
            raise RuntimeError(
                "Micropip internal error: attempted to access wheel 'requires' before downloading it?"
            )
        requires = self._dist.requires(extras)
        self._requires = requires
        return requires

    def write_dist_info(self, file: str, content: str) -> None:
        assert self.dist_info
        (self.dist_info / file).write_text(content)

    def set_installer(self) -> None:
        assert self.data
        wheel_source = "pypi" if self.digests is not None else self.url

        self.write_dist_info("PYODIDE_SOURCE", wheel_source)
        self.write_dist_info("PYODIDE_URL", self.url)
        self.write_dist_info("PYODIDE_SHA256", _generate_package_hash(self.data))
        self.write_dist_info("INSTALLER", "micropip")
        if self._requires:
            self.write_dist_info(
                "PYODIDE_REQUIRES", json.dumps(sorted(x.name for x in self._requires))
            )

    async def load_libraries(self, target: Path) -> None:
        assert self.data
        dynlibs = get_dynlibs(self.data, ".whl", target)
        await gather(*map(lambda dynlib: loadDynlib(dynlib, False), dynlibs))

    async def install(self, target: Path) -> None:
        url = self.url
        if not self.data:
            raise RuntimeError(
                "Micropip internal error: attempted to install wheel before downloading it?"
            )
        self.validate()
        self.extract(target)
        self.set_installer()
        await self.load_libraries(target)
        name = self.project_name
        assert name
        setattr(loadedPackages, name, url)


FAQ_URLS = {
    "cant_find_wheel": "https://pyodide.org/en/stable/usage/faq.html#micropip-can-t-find-a-pure-python-wheel"
}


def find_wheel(metadata: dict[str, Any], req: Requirement) -> WheelInfo:
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
            url = fileinfo["url"]
            if not url.endswith(".whl"):
                continue
            wheel = WheelInfo.from_url(url)
            if wheel.is_compatible():
                wheel.digests = fileinfo["digests"]
                return wheel

    raise ValueError(
        f"Can't find a pure Python 3 wheel for '{req}'.\n"
        f"See: {FAQ_URLS['cant_find_wheel']}\n"
        "You can use `micropip.install(..., keep_going=True)`"
        "to get a list of all packages with missing wheels."
    )


@dataclass
class Transaction:
    ctx: dict[str, str]
    ctx_extras: list[dict[str, str]]
    keep_going: bool
    deps: bool
    pre: bool
    fetch_kwargs: dict[str, str]

    locked: dict[str, PackageMetadata] = field(default_factory=dict)
    wheels: list[WheelInfo] = field(default_factory=list)
    pyodide_packages: list[PackageMetadata] = field(default_factory=list)
    failed: list[Requirement] = field(default_factory=list)

    async def gather_requirements(
        self,
        requirements: list[str],
    ) -> None:
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(self.add_requirement(requirement))

        await gather(*requirement_promises)

    async def add_requirement(self, req: str | Requirement) -> None:
        if isinstance(req, Requirement):
            return await self.add_requirement_inner(req)

        if not req.endswith(".whl"):
            return await self.add_requirement_inner(Requirement(req))

        # custom download location
        wheel = WheelInfo.from_url(req)
        if not wheel.is_compatible():
            raise ValueError(f"'{wheel.filename}' is not a pure Python 3 wheel")

        await self.add_wheel(wheel, extras=set())

    def check_version_satisfied(self, req: Requirement) -> bool:
        ver = None
        try:
            ver = importlib_version(req.name)
        except PackageNotFoundError:
            pass
        if req.name in self.locked:
            ver = self.locked[req.name].version

        if not ver:
            return False

        if req.specifier.contains(ver, prereleases=True):
            # installed version matches, nothing to do
            return True

        raise ValueError(
            f"Requested '{req}', " f"but {req.name}=={ver} is already installed"
        )

    async def add_requirement_inner(
        self,
        req: Requirement,
    ) -> None:
        """Add a requirement to the transaction.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        for e in req.extras:
            self.ctx_extras.append({"extra": e})

        if self.pre:
            req.specifier.prereleases = True

        if req.marker:
            # handle environment markers
            # https://www.python.org/dev/peps/pep-0508/#environment-markers

            # For a requirement being installed as part of an optional feature
            # via the extra specifier, the evaluation of the marker requires
            # the extra key in self.ctx to have the value specified in the
            # primary requirement.

            # The req.extras attribute is only set for the primary requirement
            # and hence has to be available during the evaluation of the
            # dependencies. Thus, we use the self.ctx_extras attribute above to
            # store all the extra values we come across during the transaction and
            # attempt the marker evaluation for all of these values. If any of the
            # evaluations return true we include the dependency.

            def eval_marker(e: dict[str, str]) -> bool:
                self.ctx.update(e)
                # need the assertion here to make mypy happy:
                # https://github.com/python/mypy/issues/4805
                assert req.marker is not None
                return req.marker.evaluate(self.ctx)

            self.ctx.update({"extra": ""})
            # The current package may have been brought into the transaction
            # without any of the optional requirement specification, but has
            # another marker, such as implementation_name. In this scenario,
            # self.ctx_extras is empty and hence the eval_marker() function
            # will not be called at all.
            if not req.marker.evaluate(self.ctx) and not any(
                [eval_marker(e) for e in self.ctx_extras]
            ):
                return
        # Is some version of this package is already installed?
        req.name = canonicalize_name(req.name)
        if self.check_version_satisfied(req):
            return

        # If there's a Pyodide package that matches the version constraint, use
        # the Pyodide package instead of the one on PyPI
        if req.name in REPODATA_PACKAGES and req.specifier.contains(
            REPODATA_PACKAGES[req.name]["version"], prereleases=True
        ):
            version = REPODATA_PACKAGES[req.name]["version"]
            self.pyodide_packages.append(
                PackageMetadata(name=req.name, version=str(version), source="pyodide")
            )
            return

        metadata = await _get_pypi_json(req.name, self.fetch_kwargs)

        try:
            wheel = find_wheel(metadata, req)
        except ValueError:
            self.failed.append(req)
            if not self.keep_going:
                raise
            else:
                return

        if self.check_version_satisfied(req):
            # Maybe while we were downloading pypi_json some other branch
            # installed the wheel?
            return

        await self.add_wheel(wheel, req.extras)

    async def add_wheel(
        self,
        wheel: WheelInfo,
        extras: set[str],
    ) -> None:
        normalized_name = canonicalize_name(wheel.name)
        self.locked[normalized_name] = PackageMetadata(
            name=wheel.name,
            version=str(wheel.version),
        )

        await wheel.download(self.fetch_kwargs)
        if self.deps:
            await self.gather_requirements(wheel.requires(extras))

        self.wheels.append(wheel)


async def install(
    requirements: str | list[str],
    keep_going: bool = False,
    deps: bool = True,
    credentials: str | None = None,
    pre: bool = False,
) -> None:
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
          Pyodide repository at :any:`indexURL <globalThis.loadPyodide>` or on PyPI

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
    if isinstance(requirements, str):
        requirements = [requirements]

    fetch_kwargs = dict()

    if credentials:
        fetch_kwargs["credentials"] = credentials

    # Note: getsitepackages is not available in a virtual environment...
    # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
    # problem is not fixed)
    from site import getsitepackages

    wheel_base = Path(getsitepackages()[0])

    transaction = Transaction(
        ctx=ctx,
        ctx_extras=[],
        keep_going=keep_going,
        deps=deps,
        pre=pre,
        fetch_kwargs=fetch_kwargs,
    )
    await transaction.gather_requirements(requirements)

    if transaction.failed:
        failed_requirements = ", ".join([f"'{req}'" for req in transaction.failed])
        raise ValueError(
            f"Can't find a pure Python 3 wheel for: {failed_requirements}\n"
            f"See: {FAQ_URLS['cant_find_wheel']}\n"
        )

    wheel_promises = []
    # Install built-in packages
    pyodide_packages = transaction.pyodide_packages
    if len(pyodide_packages):
        # Note: branch never happens in out-of-browser testing because in
        # that case REPODATA_PACKAGES is empty.
        wheel_promises.append(
            asyncio.ensure_future(
                loadPackage(to_js([name for [name, _, _] in pyodide_packages]))
            )
        )

    # Now install PyPI packages
    for wheel in transaction.wheels:
        # detect whether the wheel metadata is from PyPI or from custom location
        # wheel metadata from PyPI has SHA256 checksum digest.
        wheel_promises.append(wheel.install(wheel_base))

    await gather(*wheel_promises)


def _generate_package_hash(data: BytesIO) -> str:
    sha256_hash = hashlib.sha256()
    data.seek(0)
    while chunk := data.read(4096):
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def freeze() -> str:
    """Produce a json string which can be used as the contents of the
    ``repodata.json`` lockfile.

    If you later load pyodide with this lock file, you can use
    :any:`pyodide.loadPackage` to load packages that were loaded with `micropip` this
    time. Loading packages with :any:`pyodide.loadPackage` is much faster and you
    will always get consistent versions of all your dependencies.
    """
    from copy import deepcopy

    packages = deepcopy(REPODATA_PACKAGES)
    for dist in importlib_distributions():
        name = dist.name
        version = dist.version
        url = dist.read_text("PYODIDE_URL")
        if url is None:
            continue

        sha256 = dist.read_text("PYODIDE_SHA256")
        assert sha256
        imports = (dist.read_text("top_level.txt") or "").split()
        requires = dist.read_text("PYODIDE_REQUIRES")
        if requires:
            depends = json.loads(requires)
        else:
            depends = []

        pkg_entry: dict[str, Any] = dict(
            name=name,
            version=version,
            file_name=url,
            install_dir="site",
            sha256=sha256,
            imports=imports,
            depends=depends,
        )
        packages[canonicalize_name(name)] = pkg_entry

    # Sort
    packages = dict(sorted(packages.items()))
    package_data = {
        "info": {"arch": "wasm32", "platform": "Emscripten-1.0"},
        "packages": packages,
    }
    return json.dumps(package_data)


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

    # Add packages that are loaded through pyodide.loadPackage
    packages = PackageDict()
    for dist in importlib_distributions():
        name = dist.name
        version = dist.version
        source = dist.read_text("PYODIDE_SOURCE")
        if source is None:
            # source is None if PYODIDE_SOURCE does not exist. In this case the
            # wheel was installed manually, not via `pyodide.loadPackage` or
            # `micropip`.
            #
            # tzdata is a funny special case: we install it with pip and then
            # vendor it into our standard library. We should probably remove
            # tzdata's dist-info because it's kind of weird to have dist-info in
            # the stdlib.
            continue
        packages[name] = PackageMetadata(
            name=name,
            version=version,
            source=source,
        )

    for name, pkg_source in loadedPackages.to_py().items():
        if name in packages:
            continue

        version = REPODATA_PACKAGES[name]["version"]
        source_ = "pyodide"
        if pkg_source != "default channel":
            # Pyodide package loaded from a custom URL
            source_ = pkg_source
        packages[name] = PackageMetadata(name=name, version=version, source=source_)
    return packages
