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
from .eval import CodeRunner  # noqa: F401
from .eval import eval_code  # noqa: F401
from .eval import eval_code_async  # noqa: F401
from .eval import find_imports  # noqa: F401
from .eval import run_js  # noqa: F401
from .eval import should_quiet  # noqa: F401
from .http import open_url

DEPRECATED_LIST = {
    "CodeRunner": "eval",
    "eval_code": "eval",
    "eval_code_async": "eval",
    "find_imports": "eval",
    "should_quiet": "eval",
    "run_js": "eval",
}


if IN_BROWSER:
    import asyncio

    from .webloop import WebLoopPolicy

    policy = WebLoopPolicy()
    asyncio.set_event_loop_policy(policy)
    policy.get_event_loop()

from warnings import warn

__version__ = "0.21.0.dev0"


__all__ = [
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
    "open_url",
    "register_js_module",
    "remove_event_listener",
    "set_interval",
    "set_timeout",
    "to_js",
    "unregister_js_module",
]


def __dir__() -> list[str]:
    return __all__


for name in DEPRECATED_LIST:
    globals()[f"_deprecated_{name}"] = globals()[name]
    del globals()[name]


def __getattr__(name):
    if name in DEPRECATED_LIST:
        warn(
            f"{name} has been moved to pyodide.{DEPRECATED_LIST[name]}. "
            "Accessing it through the pyodide module is deprecated.",
            DeprecationWarning,
        )
        globals()[name] = globals()[f"_deprecated_{name}"]
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
