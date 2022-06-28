from pyodide._core import IN_BROWSER

if IN_BROWSER:
    from ._compat_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string,
        loadDynlib,
        loadedPackages,
        loadPackage,
    )
else:
    from ._compat_not_in_pyodide import (
        REPODATA_INFO,
        REPODATA_PACKAGES,
        fetch_bytes,
        fetch_string,
        loadDynlib,
        loadedPackages,
        loadPackage,
    )

__all__ = [
    "REPODATA_INFO",
    "REPODATA_PACKAGES",
    "fetch_bytes",
    "fetch_string",
    "loadedPackages",
    "loadDynlib",
    "loadPackage",
]
