import asyncio
import hashlib
import importlib
import io
import json
from pathlib import Path
import zipfile
from typing import Dict, Any, Union, List, Tuple

from packaging.requirements import Requirement
from packaging.version import Version

# Provide stubs for testing in native python
try:
    import pyodide_js
    from pyodide import to_js

    IN_BROWSER = True
except ImportError:
    IN_BROWSER = False

if IN_BROWSER:
    # In practice, this is the `site-packages` directory.
    WHEEL_BASE = Path(__file__).parent
else:
    WHEEL_BASE = Path(".") / "wheels"

if IN_BROWSER:
    from js import fetch

    async def _get_url(url):
        resp = await fetch(url)
        if not resp.ok:
            raise OSError(
                f"Request for {url} failed with status {resp.status}: {resp.statusText}"
            )
        return io.BytesIO(await resp.arrayBuffer())


else:
    from urllib.request import urlopen

    async def _get_url(url):
        with urlopen(url) as fd:
            content = fd.read()
        return io.BytesIO(content)


if IN_BROWSER:
    from asyncio import gather
else:
    # asyncio.gather will schedule any coroutines to run on the event loop but
    # we want to avoid using the event loop at all. Instead just run the
    # coroutines in sequence.
    async def gather(*coroutines):  # type: ignore
        result = []
        for coroutine in coroutines:
            result.append(await coroutine)
        return result


if IN_BROWSER:
    from pyodide_js import loadedPackages
else:

    class loadedPackages:  # type: ignore
        pass


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
    with zipfile.ZipFile(fd) as zf:
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
    wheel = await _get_url(url)
    _validate_wheel(wheel, fileinfo)
    _extract_wheel(wheel)
    setattr(loadedPackages, name, url)


class _PackageManager:
    def __init__(self):
        if IN_BROWSER:
            self.builtin_packages = pyodide_js._module.packages.versions.to_py()
        else:
            self.builtin_packages = {}
        self.installed_packages = {}

    async def install(self, requirements: Union[str, List[str]], ctx=None):
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

        wheel_promises = []

        # Install built-in packages
        pyodide_packages = transaction["pyodide_packages"]
        if len(pyodide_packages):
            # Note: branch never happens in out-of-browser testing because in
            # that case builtin_packages is empty.
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

    async def add_requirement(self, requirement: str, ctx, transaction):
        """Add a requirement to the transaction.

        See PEP 508 for a description of the requirements.
        https://www.python.org/dev/peps/pep-0508
        """
        if requirement.endswith(".whl"):
            # custom download location
            name, wheel, version = _parse_wheel_url(requirement)
            transaction["wheels"].append((name, wheel, version))
            return

        req = Requirement(requirement)

        # If there's a Pyodide package that matches the version constraint, use
        # the Pyodide package instead of the one on PyPI
        if (
            req.name in self.builtin_packages
            and self.builtin_packages[req.name] in req.specifier
        ):
            version = self.builtin_packages[req.name]
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
        transaction["locked"][req.name] = ver

        recurs_reqs = metadata.get("info", {}).get("requires_dist") or []
        for recurs_req in recurs_reqs:
            await self.add_requirement(recurs_req, ctx, transaction)

        transaction["wheels"].append((req.name, wheel, ver))

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
