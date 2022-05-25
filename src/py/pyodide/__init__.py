# When the pyodide package is imported, both the js and the pyodide_js modules
# will be available to import from. Not all functions in pyodide_js will work
# until after pyodide is first imported, imported functions from pyodide_js
# should not be used at import time. It is fine to use js functions at import
# time.
#
# All pure Python code that does not require js or pyodide_js should go in
# the _pyodide package.
#
# This package is imported by the test suite as well, and currently we don't use
# pytest mocks for js or pyodide_js, so make sure to test "if IN_BROWSER" before
# importing from these.

from _pyodide._base import (
    CodeRunner,
    eval_code,
    eval_code_async,
    find_imports,
    should_quiet,
)
from _pyodide._importhook import register_js_module, unregister_js_module

from . import _state  # noqa: F401
from ._browser_apis import (
    add_event_listener,
    clear_interval,
    clear_timeout,
    remove_event_listener,
    set_interval,
    set_timeout,
)
from ._core import (
    IN_BROWSER,
    ConversionError,
    JsException,
    JsProxy,
    create_once_callable,
    create_proxy,
    destroy_proxies,
    to_js,
)
from ._run_js import run_js
from .http import open_url

if IN_BROWSER:
    import asyncio

    from .webloop import WebLoopPolicy

    asyncio.set_event_loop_policy(WebLoopPolicy())


__version__ = "0.20.0"

__all__ = [
    "CodeRunner",
    "ConversionError",
    "JsException",
    "JsProxy",
    "add_event_listener",
    "clear_interval",
    "clear_timeout",
    "console",
    "create_once_callable",
    "create_proxy",
    "destroy_proxies",
    "eval_code",
    "eval_code_async",
    "find_imports",
    "open_url",
    "register_js_module",
    "remove_event_listener",
    "run_js",
    "set_interval",
    "set_timeout",
    "should_quiet",
    "to_js",
    "unregister_js_module",
]


def __dir__() -> list[str]:
    return __all__
