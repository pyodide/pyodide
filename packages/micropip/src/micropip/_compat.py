from pyodide import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        gather,
        fetch_bytes,
        fetch_string,
        WHEEL_BASE,
        BUILTIN_PACKAGES,
        loadedPackages,
    )
else:
    from ._compat_not_in_pyodide import (
        gather,
        fetch_bytes,
        fetch_string,
        WHEEL_BASE,
        BUILTIN_PACKAGES,
        loadedPackages,
    )

__all__ = [
    "gather",
    "fetch_bytes",
    "fetch_string",
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
]
