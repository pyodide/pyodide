import sys

IN_BROWSER = "_pyodide_core" in sys.modules


if IN_BROWSER:
    import _pyodide_core
    from _pyodide_core import (
        ConversionError,
        JsException,
        create_once_callable,
        create_proxy,
        destroy_proxies,
        to_js,
    )

    import _pyodide._core_docs

    _pyodide._core_docs._js_flags = _pyodide_core.js_flags
else:
    from _pyodide._core_docs import (
        ConversionError,
        JsException,
        create_once_callable,
        create_proxy,
        destroy_proxies,
        to_js,
    )

from _pyodide._core_docs import (
    JsArray,
    JsAsyncGenerator,
    JsAsyncIterable,
    JsAsyncIterator,
    JsBuffer,
    JsDoubleProxy,
    JsFetchResponse,
    JsGenerator,
    JsIterable,
    JsIterator,
    JsMap,
    JsMutableMap,
    JsPromise,
    JsProxy,
    JsTypedArray,
)

__all__ = [
    "JsProxy",
    "JsDoubleProxy",
    "JsArray",
    "JsGenerator",
    "JsAsyncGenerator",
    "JsIterable",
    "JsAsyncIterable",
    "JsIterator",
    "JsException",
    "create_proxy",
    "create_once_callable",
    "to_js",
    "ConversionError",
    "destroy_proxies",
    "JsPromise",
    "JsBuffer",
    "JsTypedArray",
    "JsArray",
    "JsFetchResponse",
    "JsMap",
    "JsMutableMap",
    "JsAsyncIterator",
]
