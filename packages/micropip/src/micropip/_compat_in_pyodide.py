from pyodide._core import IN_BROWSER
from pyodide.http import pyfetch

try:
    import pyodide_js
    from pyodide_js import loadedPackages

    BUILTIN_PACKAGES = pyodide_js._api.packages.to_py()
except ImportError:
    if IN_BROWSER:
        raise
    # Otherwise, this is pytest test collection so let it go.


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
    return await (await pyfetch(url, **kwargs)).bytes()


async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
    return await (await pyfetch(url, **kwargs)).string()


__all__ = [
    "fetch_bytes",
    "fetch_string",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "pyodide_js",
]
