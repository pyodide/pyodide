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

    # This is intentionally opaque to static analysis tools (e.g., mypy)
    #
    # Note:
    #   Normally one would handle this by adding type stubs for
    #   _pyodide_core, but since we already are getting the correct types
    #   from _core_docs, adding a type stub would introduce a redundancy
    #   that would be difficult to maintain.
    for t in [
        "JsException",
        "create_once_callable",
        "create_proxy",
        "destroy_proxies",
        "to_js",
    ]:
        globals()[t] = getattr(_pyodide_core, t)

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
