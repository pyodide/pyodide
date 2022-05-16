import tempfile
from pathlib import Path
from typing import Any

import pyodide_js

# Provide stubs for testing in native python
WHEEL_BASE = Path(tempfile.mkdtemp())
BUILTIN_PACKAGES: dict[str, dict[str, Any]] = pyodide_js._api.packages.to_py()


class loadedPackages_:
    @staticmethod
    def to_py():
        return {}


loadedPackages: Any = loadedPackages_


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


__all__ = [
    "gather",
    "fetch_bytes",
    "fetch_string",
    "WHEEL_BASE",
    "BUILTIN_PACKAGES",
    "loadedPackages",
    "pyodide_js",
]
