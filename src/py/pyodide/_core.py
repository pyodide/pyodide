import sys

IN_BROWSER = "_pyodide_core" in sys.modules

if IN_BROWSER:
    from _pyodide_core import (
        ConversionError,
        JsException,
        JsProxy,
        create_once_callable,
        create_proxy,
        destroy_proxies,
        to_js,
    )
else:
    from _pyodide._core_docs import (
        ConversionError,
        JsException,
        JsProxy,
        create_once_callable,
        create_proxy,
        destroy_proxies,
        to_js,
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
