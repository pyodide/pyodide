import asyncio
import hashlib
import importlib
import json
import warnings
from asyncio import gather
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import distributions as importlib_distributions
from importlib.metadata import version as importlib_version
from pathlib import Path
from sysconfig import get_platform
from typing import IO, Any
from urllib.parse import ParseResult, urlparse
from zipfile import ZipFile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import Tag, sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from pyodide._package_loader import get_dynlibs, wheel_dist_info_dir
from pyodide.ffi import to_js

from ._compat import (
    REPODATA_INFO,
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
    parsed_url: ParseResult
    project_name: str | None = None
    digests: dict[str, str] | None = None
    data: IO[bytes] | None = None
    _dist: Any = None
    dist_info: Path | None = None
    _requires: list[Requirement] | None = None

    @staticmethod
    def from_url(url: str) -> "WheelInfo":
        """Parse wheels URL and extract available metadata

        See https://www.python.org/dev/peps/pep-0427/#file-name-convention
        """
        parsed_url = urlparse(url)
        file_name = Path(parsed_url.path).name
        name, version, build, tags = parse_wheel_filename(file_name)
        return WheelInfo(
            name=name,
            version=version,
            filename=file_name,
            build=build,
            tags=tags,
            url=url,
            parsed_url=parsed_url,
        )

    def is_compatible(self):
        if self.filename.endswith("py3-none-any.whl"):
            return True
        for tag in sys_tags():
            if tag in self.tags:
                return True
        return False

    def check_compatible(self):
        if self.is_compatible():
            return
        tag: Tag = next(iter(self.tags))
        if "emscripten" not in tag.platform:
            raise ValueError(
                f"Wheel platform '{tag.platform}' is not compatible with "
                f"Pyodide's platform '{get_platform()}'"
            )

        def platform_to_version(platform: str) -> str:
            return (
                platform.replace("-", "_")
                .removeprefix("emscripten_")
                .removesuffix("_wasm32")
                .replace("_", ".")
            )

        wheel_emscripten_version = platform_to_version(tag.platform)
        pyodide_emscripten_version = platform_to_version(get_platform())
        if wheel_emscripten_version != pyodide_emscripten_version:
            raise ValueError(
                f"Wheel was built with Emscripten v{wheel_emscripten_version} but "
                f"Pyodide was built with Emscripten v{pyodide_emscripten_version}"
            )

        abi_incompatible = True
        from sys import version_info

        version = f"{version_info.major}{version_info.minor}"
        abis = ["abi3", f"cp{version}"]
        for tag in self.tags:
            if tag.abi in abis:
                abi_incompatible = False
            break
        if abi_incompatible:
            abis_string = ",".join({tag.abi for tag in self.tags})
            raise ValueError(
                f"Wheel abi '{abis_string}' is not supported. Supported abis are 'abi3' and 'cp{version}'."
            )

        raise ValueError(
            f"Wheel interpreter version '{tag.interpreter}' is not supported."
        )

    async def _fetch_bytes(self, fetch_kwargs):
        try:
            return await fetch_bytes(self.url, fetch_kwargs)
        except OSError as e:
            if self.parsed_url.hostname in [
                "files.pythonhosted.org",
                "cdn.jsdelivr.net",
            ]:
                raise e
            else:
                raise ValueError(
                    f"Can't fetch wheel from '{self.url}'. "
                    "One common reason for this is when the server blocks "
                    "Cross-Origin Resource Sharing (CORS). "
                    "Check if the server is sending the correct 'Access-Control-Allow-Origin' header."
                ) from e

    async def download(self, fetch_kwargs):
        data = await self._fetch_bytes(fetch_kwargs)
        self.data = data
        with ZipFile(data) as zip_file:
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
        sha256_expected = self.digests["sha256"]
        assert self.data
        sha256_actual = _generate_package_hash(self.data)
        if sha256_actual != sha256_expected:
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
        name = self.project_name
        assert name
        setattr(loadedPackages, name, wheel_source)

    async def load_libraries(self, target: Path) -> None:
        assert self.data
        dynlibs = get_dynlibs(self.data, ".whl", target)
        await gather(*map(lambda dynlib: loadDynlib(dynlib, False), dynlibs))

    async def install(self, target: Path) -> None:
        if not self.data:
            raise RuntimeError(
                "Micropip internal error: attempted to install wheel before downloading it?"
            )
        self.validate()
        self.extract(target)
        await self.load_libraries(target)
        self.set_installer()


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
        if str(ver) not in releases:
            pkg_name = metadata.get("info", {}).get("name", "UNKNOWN")
            warnings.warn(
                f"The package '{pkg_name}' contains an invalid version: '{ver}'. This version will be skipped"
            )
            continue

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
        wheel.check_compatible()

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

    If a package is not found in the Pyodide repository it will be loaded from
    PyPI. Micropip can only load pure Python packages or for packages with C
    extensions that are built for Pyodide.

    When used in web browsers, downloads from PyPI will be cached. When run in
    Node.js, packages are currently not cached, and will be re-downloaded each
    time ``micropip.install`` is run.

    Parameters
    ----------
    requirements : ``str | List[str]``

        A requirement or list of requirements to install. Each requirement is a
        string, which should be either a package name or a wheel URI:

        - If the requirement does not end in ``.whl``, it will be interpreted as
          a package name. A package with this name must either be present
          in the Pyodide lock file or on PyPI.

        - If the requirement ends in ``.whl``, it is a wheel URI. The part of
          the requirement after the last ``/``  must be a valid wheel name in
          compliance with the `PEP 427 naming convention
          <https://www.python.org/dev/peps/pep-0427/#file-format>`_.

        - If a wheel URI starts with ``emfs:``, it will be interpreted as a path
          in the Emscripten file system (Pyodide's file system). E.g.,
          `emfs:../relative/path/wheel.whl` or `emfs:/absolute/path/wheel.whl`.
          In this case, only .whl files are supported.

        - If a wheel URI requirement starts with ``http:`` or ``https:`` it will
          be interpreted as a URL.

        - In node, you can access the native file system using a URI that starts
          with ``file:``. In the browser this will not work.


    keep_going : ``bool``, default: False

        This parameter decides the behavior of the micropip when it encounters a
        Python package without a pure Python wheel while doing dependency
        resolution:

        - If ``False``, an error will be raised on first package with a missing
          wheel.

        - If ``True``, the micropip will keep going after the first error, and
          report a list of errors at the end.

    deps : ``bool``, default: True

        If ``True``, install dependencies specified in METADATA file for each
        package. Otherwise do not install dependencies.

    credentials : ``Optional[str]``

        This parameter specifies the value of ``credentials`` when calling the
        `fetch() <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`__
        function which is used to download the package.

        When not specified, ``fetch()`` is called without ``credentials``.

    pre : ``bool``, default: False

        If ``True``, include pre-release and development versions. By default,
        micropip only finds stable versions.

    Returns
    -------
    ``Future``

        A ``Future`` that resolves to ``None`` when all packages have been
        downloaded and installed.
    """
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
    importlib.invalidate_caches()


def _generate_package_hash(data: IO[bytes]) -> str:
    sha256_hash = hashlib.sha256()
    data.seek(0)
    while chunk := data.read(4096):
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def freeze() -> str:
    """Produce a json string which can be used as the contents of the
    ``repodata.json`` lock file.

    If you later load Pyodide with this lock file, you can use
    :any:`pyodide.loadPackage` to load packages that were loaded with `micropip`
    this time. Loading packages with :any:`pyodide.loadPackage` is much faster
    and you will always get consistent versions of all your dependencies.

    You can use your custom lock file by passing an appropriate url to the
    `lockFileURL` argument to :any:`loadPyodide <globalThis.loadPyodide>`.
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
        "info": REPODATA_INFO,
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

        if name in REPODATA_PACKAGES:
            version = REPODATA_PACKAGES[name]["version"]
            source_ = "pyodide"
            if pkg_source != "default channel":
                # Pyodide package loaded from a custom URL
                source_ = pkg_source
        else:
            # TODO: calculate version from wheel metadata
            version = "unknown"
            source_ = pkg_source
        packages[name] = PackageMetadata(name=name, version=version, source=source_)
    return packages
