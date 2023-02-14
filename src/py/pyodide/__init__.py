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
__version__ = "0.22.0"

__all__ = ["__version__", "console", "code", "ffi", "http", "webloop"]

from typing import Any

from . import _state  # noqa: F401
from .code import (
    CodeRunner,  # noqa: F401
    eval_code,  # noqa: F401
    eval_code_async,  # noqa: F401
    find_imports,  # noqa: F401
    should_quiet,  # noqa: F401
)
from .ffi import (
    ConversionError,  # noqa: F401
    JsException,  # noqa: F401
    JsProxy,  # noqa: F401
    create_once_callable,  # noqa: F401
    create_proxy,  # noqa: F401
    destroy_proxies,  # noqa: F401
    register_js_module,  # noqa: F401
    to_js,  # noqa: F401
    unregister_js_module,  # noqa: F401
)
from .http import open_url  # noqa: F401

DEPRECATED_LIST = {
    "CodeRunner": "code",
    "eval_code": "code",
    "eval_code_async": "code",
    "find_imports": "code",
    "should_quiet": "code",
    "open_url": "http",
    "ConversionError": "ffi",
    "JsException": "ffi",
    "JsProxy": "ffi",
    "create_once_callable": "ffi",
    "create_proxy": "ffi",
    "destroy_proxies": "ffi",
    "to_js": "ffi",
    "register_js_module": "ffi",
    "unregister_js_module": "ffi",
}


from .webloop import _initialize_event_loop

_initialize_event_loop()
del _initialize_event_loop


def __dir__() -> list[str]:
    return __all__


for name in DEPRECATED_LIST:
    globals()[f"_deprecated_{name}"] = globals()[name]
    del globals()[name]


def __getattr__(name: str) -> Any:
    if name in DEPRECATED_LIST:
        from warnings import warn

        warn(
            f"pyodide.{name} has been moved to pyodide.{DEPRECATED_LIST[name]}.{name} "
            "Accessing it through the pyodide module is deprecated.",
            FutureWarning,
        )
        # Put the name back so we won't warn next time this name is accessed
        globals()[name] = globals()[f"_deprecated_{name}"]
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
