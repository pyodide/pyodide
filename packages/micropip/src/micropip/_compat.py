from pyodide import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        BUILTIN_PACKAGES,
        WHEEL_BASE,
        fetch_bytes,
        fetch_string,
        gather,
        loadedPackages,
        pyodide_js,
    )
else:
    from ._compat_not_in_pyodide import (  # type: ignore[no-redef]
        BUILTIN_PACKAGES,
        WHEEL_BASE,
        fetch_bytes,
        fetch_string,
        gather,
        loadedPackages,
        pyodide_js,
    )

__all__ = [
    "gather",
    "fetch_bytes",
    "fetch_string",
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "pyodide_js",
]
