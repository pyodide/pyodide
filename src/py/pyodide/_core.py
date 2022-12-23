import sys

IN_BROWSER = "_pyodide_core" in sys.modules

from _pyodide._core_docs import (
    ConversionError,
    JsArray,
    JsAsyncGenerator,
    JsAsyncIterable,
    JsAsyncIterator,
    JsBuffer,
    JsCallable,
    JsDomElement,
    JsDoubleProxy,
    JsException,
    JsFetchResponse,
    JsGenerator,
    JsIterable,
    JsIterator,
    JsMap,
    JsMutableMap,
    JsPromise,
    JsProxy,
    JsTypedArray,
    create_once_callable,
    create_proxy,
    destroy_proxies,
    to_js,
)

if IN_BROWSER:
    import _pyodide_core

    import _pyodide._core_docs

    for t in [
        "ConversionError",
        "JsException",
        "create_once_callable",
        "create_proxy",
        "destroy_proxies",
        "to_js",
    ]:
        globals()[t] = _pyodide_core[t]

    _pyodide._core_docs._js_flags = _pyodide_core.js_flags


__all__ = [
    "ConversionError",
    "JsArray",
    "JsAsyncGenerator",
    "JsAsyncIterable",
    "JsAsyncIterator",
    "JsBuffer",
    "JsDoubleProxy",
    "JsException",
    "JsFetchResponse",
    "JsGenerator",
    "JsIterable",
    "JsIterator",
    "JsMap",
    "JsMutableMap",
    "JsPromise",
    "JsProxy",
    "JsDomElement",
    "JsCallable",
    "JsTypedArray",
    "create_once_callable",
    "create_proxy",
    "destroy_proxies",
    "to_js",
]
