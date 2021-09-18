from _pyodide._core_docs import (
    JsProxy,
    JsException,
    create_once_callable,
    create_proxy,
    to_js,
    ConversionError,
    destroy_proxies,
)

__all__ = [
    "JsProxy",
    "JsException",
    "create_once_callable",
    "create_proxy",
    "to_js",
    "ConversionError",
    "destroy_proxies",
]

IN_BROWSER = False
