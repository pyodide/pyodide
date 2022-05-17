import tempfile
from pathlib import Path
from typing import Any

# Provide stubs for testing in native python
WHEEL_BASE = Path(tempfile.mkdtemp())
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


# asyncio.gather will schedule any coroutines to run on the event loop but
# we want to avoid using the event loop at all. Instead just run the
# coroutines in sequence.
# TODO: Use an asyncio testing framework to avoid this
async def gather(*coroutines):
    result = []
    for coroutine in coroutines:
        result.append(await coroutine)
    return result


class pyodide_js_:
    def __get__(self, attr):
        raise RuntimeError(f"Attempted to access property '{attr}' on pyodide_js dummy")


pyodide_js: Any = pyodide_js_()


__all__ = [
    "gather",
    "fetch_bytes",
    "fetch_string",
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "pyodide_js",
]
