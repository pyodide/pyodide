from pyodide._core import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        BUILTIN_PACKAGES,
        WHEEL_BASE,
        fetch_bytes,
        fetch_string,
        loadedPackages,
        pyodide_js,
    )
else:
    from ._compat_not_in_pyodide import (
        BUILTIN_PACKAGES,
        WHEEL_BASE,
        fetch_bytes,
        fetch_string,
        loadedPackages,
        pyodide_js,
    )

__all__ = [
    "fetch_bytes",
    "fetch_string",
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "pyodide_js",
]
