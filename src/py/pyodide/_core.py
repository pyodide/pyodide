import sys

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from _pyodide_core import (
        ConversionError,
        create_proxy,
        create_once_callable,
        JsProxy,
        JsException,
        to_js,
        destroy_proxies,
    )
else:
    from _pyodide._core_docs import (
        ConversionError,
        create_proxy,
        create_once_callable,
        JsProxy,
        JsException,
        to_js,
        destroy_proxies,
    )


__all__ = [
    "JsProxy",
    "JsException",
    "create_proxy",
    "create_once_callable",
    "to_js",
    "ConversionError",
    "destroy_proxies",
]
