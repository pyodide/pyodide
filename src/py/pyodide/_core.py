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
        run_js,
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
        run_js,
        to_js,
    )


__all__ = [
    "ConversionError",
    "JsException",
    "JsProxy",
    "create_once_callable",
    "create_proxy",
    "destroy_proxies",
    "to_js",
    "run_js",
]
