import asyncio
import hashlib
import importlib
import io
import json
from pathlib import Path
import zipfile
from typing import Dict, Any, Union, List, Tuple

from distlib import markers, util, version

import sys

# Provide stubs for testing in native python
try:
    from js import pyodide as js_pyodide

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


async def _get_pypi_json(pkgname):
    url = f"https://pypi.org/pypi/{pkgname}/json"
    fd = await _get_url(url)
    return json.load(fd)


def _parse_wheel_url(url: str) -> Tuple[str, Dict[str, Any], str]:
    """Parse wheels url and extract available metadata

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


class _PackageManager:
    version_scheme = version.get_scheme("normalized")

    def __init__(self):
        if IN_BROWSER:
            self.builtin_packages = js_pyodide._module.packages.dependencies.to_py()
        else:
            self.builtin_packages = {}
        self.installed_packages = {}

    async def install(self, requirements: Union[str, List[str]], ctx=None):
        if ctx is None:
            ctx = {"extra": None}

        complete_ctx = dict(markers.DEFAULT_CONTEXT)
        complete_ctx.update(ctx)

        if isinstance(requirements, str):
            requirements = [requirements]

        transaction: Dict[str, Any] = {
            "wheels": [],
            "pyodide_packages": set(),
            "locked": dict(self.installed_packages),
        }
        requirement_promises = []
        for requirement in requirements:
            requirement_promises.append(
                self.add_requirement(requirement, complete_ctx, transaction)
            )

        await gather(*requirement_promises)

        wheel_promises = []

        # Install built-in packages
        pyodide_packages = transaction["pyodide_packages"]
        if len(pyodide_packages):
            # Note: branch never happens in out-of-browser testing because we
            # report that all dependencies are empty.
            self.installed_packages.update(dict((k, None) for k in pyodide_packages))
            wheel_promises.append(js_pyodide.loadPackage(list(pyodide_packages)))

        # Now install PyPI packages
        for name, wheel, ver in transaction["wheels"]:
            wheel_promises.append(_install_wheel(name, wheel))
            self.installed_packages[name] = ver
        await gather(*wheel_promises)
        return f'Installed {", ".join(self.installed_packages.keys())}'

    async def add_requirement(self, requirement: str, ctx, transaction):
        if requirement.endswith(".whl"):
            # custom download location
            name, wheel, version = _parse_wheel_url(requirement)
            transaction["wheels"].append((name, wheel, version))
            return

        req = util.parse_requirement(requirement)

        # If it's a Pyodide package, use that instead of the one on PyPI
        if req.name in self.builtin_packages:
            transaction["pyodide_packages"].add(req.name)
            return

        if req.marker:
            if not markers.evaluator.evaluate(req.marker, ctx):
                return

        matcher = self.version_scheme.matcher(req.requirement)

        # If we already have something that will work, don't
        # fetch again
        for name, ver in transaction["locked"].items():
            if name == req.name:
                if matcher.match(ver):
                    break
                else:
                    raise ValueError(
                        f"Requested '{requirement}', "
                        f"but {name}=={ver} is already installed"
                    )
        else:
            metadata = await _get_pypi_json(req.name)
            wheel, ver = self.find_wheel(metadata, req)
            transaction["locked"][req.name] = ver

            recurs_reqs = metadata.get("info", {}).get("requires_dist") or []
            for recurs_req in recurs_reqs:
                await self.add_requirement(recurs_req, ctx, transaction)

            transaction["wheels"].append((req.name, wheel, ver))

    def find_wheel(self, metadata, req):
        releases = []
        for ver, files in metadata.get("releases", {}).items():
            ver = self.version_scheme.suggest(ver)
            if ver is not None:
                releases.append((ver, files))

        def version_number(release):
            return version.NormalizedVersion(release[0])

        releases = sorted(releases, key=version_number, reverse=True)
        matcher = self.version_scheme.matcher(req.requirement)
        for ver, meta in releases:
            if matcher.match(ver):
                for fileinfo in meta:
                    if fileinfo["filename"].endswith("py3-none-any.whl"):
                        return fileinfo, ver

        raise ValueError(f"Couldn't find a pure Python 3 wheel for '{req.requirement}'")


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

        A requirement or list of requirements to install. Each requirement is a string.

        - If the requirement ends in ``.whl``, the file will be interpreted as a url.
          The file must be a wheel named in compliance with the
          `PEP 427 naming convention <https://www.python.org/dev/peps/pep-0427/#file-format>`_.
        - A package name. A package by this name must either be present in the Pyodide
          repository at ``languagePluginUrl`` or on PyPi.

    Returns
    -------
    A Future that resolves when all packages have been downloaded and installed.
    """
    importlib.invalidate_caches()
    return asyncio.ensure_future(PACKAGE_MANAGER.install(requirements))


__all__ = ["install"]


if __name__ == "__main__":
    install("snowballstemmer")
