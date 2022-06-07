from pyodide._core import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        BUILTIN_PACKAGES,
        fetch_bytes,
        fetch_string,
        loadDynlib,
        loadedPackages,
        loadPackage,
    )
else:
    from ._compat_not_in_pyodide import (
        BUILTIN_PACKAGES,
        fetch_bytes,
        fetch_string,
        loadDynlib,
        loadedPackages,
        loadPackage,
    )

__all__ = [
    "fetch_bytes",
    "fetch_string",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "loadDynlib",
    "loadPackage",
]
