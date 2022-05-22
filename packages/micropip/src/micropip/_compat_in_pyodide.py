from pathlib import Path

from pyodide.http import pyfetch

try:
    import pyodide_js
    from pyodide_js import loadedPackages
    from pyodide_js._api import loadDynlib  # type: ignore[import]

    BUILTIN_PACKAGES = pyodide_js._api.packages.to_py()

    # Random note: getsitepackages is not available in a virtual environment...
    # See https://github.com/pypa/virtualenv/issues/228 (issue is closed but
    # problem is not fixed)
    from site import getsitepackages

    WHEEL_BASE = Path(getsitepackages()[0])
except ImportError:
    from pyodide import IN_BROWSER

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
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "loadDynlib",
    "pyodide_js",
]
