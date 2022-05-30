from typing import Any

BUILTIN_PACKAGES: dict[str, dict[str, Any]] = {}


class loadedPackages:
    @staticmethod
    def to_py():
        return {}


from urllib.request import Request, urlopen


async def fetch_bytes(url: str, kwargs: dict[str, str]) -> bytes:
    return urlopen(Request(url, headers=kwargs)).read()


async def fetch_string(url: str, kwargs: dict[str, str]) -> str:
    return (await fetch_bytes(url, kwargs)).decode()


async def loadDynlib(dynlib: str, is_shared_lib: bool) -> None:
    pass


class pyodide_js_:
    def __get__(self, attr):
        raise RuntimeError(f"Attempted to access property '{attr}' on pyodide_js dummy")


from pyodide import __version__

try:
    from pyodide_build.common import platform

    # Build package.json data.
    [platform, _, arch] = platform().rpartition("_")

    PACKAGE_INFO = {"arch": arch, "platform": platform, "version": __version__}
except ImportError:
    PACKAGE_INFO = {}


def loadPackage(packages: str | list[str]) -> None:
    pass


__all__ = [
    "loadDynlib",
    "fetch_bytes",
    "fetch_string",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "loadPackage",
    "PACKAGE_INFO",
]
