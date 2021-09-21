import asyncio
import hashlib
import importlib
import io
import json

from packaging.requirements import Requirement
from packaging.version import Version
from packaging.markers import default_environment

from pathlib import Path
from typing import Dict, Any, Union, List, Tuple
from zipfile import ZipFile

from .externals.pip._internal.utils.wheel import pkg_resources_distribution_for_wheel

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
    WHEEL_BASE = Path(".") / "wheels"

if IN_BROWSER:
    BUILTIN_PACKAGES = pyodide_js._module.packages.to_py()
else:
    BUILTIN_PACKAGES = {}

if IN_BROWSER:
    from pyodide_js import loadedPackages
else:

    class loadedPackages:  # type: ignore
        pass


if IN_BROWSER:
    from js import fetch
else:
    from urllib.request import urlopen, Request

    async def fetch(url, headers={}):
        fd = urlopen(Request(url, headers=headers))
        fd.statusText = fd.reason

        async def arrayBuffer():
            class Temp:
                def to_py():
                    return fd.read()

            return Temp

        fd.arrayBuffer = arrayBuffer
        return fd


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


async def _get_url(url):
    resp = await fetch(url)
    if resp.status >= 400:
        raise OSError(
            f"Request for {url} failed with status {resp.status}: {resp.statusText}"
        )
    return io.BytesIO((await resp.arrayBuffer()).to_py())


async def _get_pypi_json(pkgname):
    url = f"https://pypi.org/pypi/{pkgname}/json"
    fd = await _get_url(url)
    return json.load(fd)


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
        # from a different location than PyPi.
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
        self.installed_packages = {}

    async def gather_requirements(self, requirements: Union[str, List[str]], ctx=None):
        ctx = ctx or default_environment()
        ctx.setdefault("extra", None)
        if isinstance(requirements, str):
            requirements = [requirements]

        transaction: Dict[str, Any] = {
            "wheels": [],
            "pyodide_packages": [],
            "locked": dict(self.installed_packages),
        }
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(
                self.add_requirement(requirement, ctx, transaction)
            )

        await gather(*requirement_promises)
        return transaction

    async def install(self, requirements: Union[str, List[str]], ctx=None):
        transaction = await self.gather_requirements(requirements, ctx)
        wheel_promises = []
        # Install built-in packages
        pyodide_packages = transaction["pyodide_packages"]
        if len(pyodide_packages):
            # Note: branch never happens in out-of-browser testing because in
            # that case BUILTIN_PACKAGES is empty.
            self.installed_packages.update(pyodide_packages)
            wheel_promises.append(
                asyncio.ensure_future(
                    pyodide_js.loadPackage(
                        to_js([name for [name, _] in pyodide_packages])
                    )
                )
            )

        # Now install PyPI packages
        for name, wheel, ver in transaction["wheels"]:
            wheel_promises.append(_install_wheel(name, wheel))
            self.installed_packages[name] = ver
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
            transaction["pyodide_packages"].append((req.name, version))
            return

        if req.marker:
            # handle environment markers
            # https://www.python.org/dev/peps/pep-0508/#environment-markers
            if not req.marker.evaluate(ctx):
                return

        # Is some version of this package is already installed?
        if req.name in transaction["locked"]:
            ver = transaction["locked"][req.name]
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
        await self.add_wheel(req.name, wheel, ver, req.extras, ctx, transaction)

    async def add_wheel(self, name, wheel, version, extras, ctx, transaction):
        transaction["locked"][name] = version
        response = await fetch(wheel["url"])
        wheel_bytes = (await response.arrayBuffer()).to_py()
        wheel["wheel_bytes"] = wheel_bytes

        with ZipFile(io.BytesIO(wheel_bytes)) as zip_file:  # type: ignore
            dist = pkg_resources_distribution_for_wheel(zip_file, name, "???")
        for recurs_req in dist.requires(extras):
            await self.add_requirement(recurs_req, ctx, transaction)

        transaction["wheels"].append((name, wheel, version))

    def find_wheel(self, metadata, req: Requirement):
        releases = metadata.get("releases", {})
        candidate_versions = sorted(
            (Version(v) for v in req.specifier.filter(releases)),  # type: ignore
            reverse=True,
        )
        for ver in candidate_versions:
            release = releases[str(ver)]
            for fileinfo in release:
                if fileinfo["filename"].endswith("py3-none-any.whl"):
                    return fileinfo, ver

        raise ValueError(f"Couldn't find a pure Python 3 wheel for '{req}'")


# Make PACKAGE_MANAGER singleton
PACKAGE_MANAGER = _PackageManager()
del _PackageManager


def install(requirements: Union[str, List[str]]):
    """Install the given package and all of its dependencies.

    See :ref:`loading packages <loading_packages>` for more information.

    This only works for packages that are either pure Python or for packages
    with C extensions that are built in Pyodide. If a pure Python package is not
    found in the Pyodide repository it will be loaded from PyPi.

    When used in web browsers, downloads from PyPi will be cached. When run in
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
          Pyodide repository at `indexURL <globalThis.loadPyodide>` or on PyPi

    Returns
    -------
    ``Future``

        A ``Future`` that resolves to ``None`` when all packages have been
        downloaded and installed.
    """
    importlib.invalidate_caches()
    return asyncio.ensure_future(PACKAGE_MANAGER.install(requirements))


__all__ = ["install"]


if __name__ == "__main__":
    install("snowballstemmer")
