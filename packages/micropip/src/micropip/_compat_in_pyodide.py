from pyodide._core import IN_BROWSER
from pyodide.http import pyfetch

try:
    import pyodide_js
    from pyodide_js import loadedPackages, loadPackage
    from pyodide_js._api import loadBinaryFile, loadDynlib  # type: ignore[import]

    REPODATA_PACKAGES = pyodide_js._api.repodata_packages.to_py()
    REPODATA_INFO = pyodide_js._api.repodata_info.to_py()
except ImportError:
    if IN_BROWSER:
        raise
    # Otherwise, this is pytest test collection so let it go.


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
    if url.startswith("file://"):
        return (await loadBinaryFile("", url)).to_bytes()
    return await (await pyfetch(url, **kwargs)).bytes()


async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
    return await (await pyfetch(url, **kwargs)).string()


__all__ = [
    "fetch_bytes",
    "fetch_string",
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "loadedPackages",
    "loadDynlib",
    "loadPackage",
]
