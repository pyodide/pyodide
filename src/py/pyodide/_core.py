import sys

IN_BROWSER = True
if "_pyodide_core" not in sys.modules:
    from _pyodide import _core_docs as _pyodide_core

    sys.modules["_pyodide_core"] = _pyodide_core
    IN_BROWSER = False

from _pyodide_core import (
    JsProxy,
    JsException,
    create_proxy,
    create_once_callable,
    to_js,
)

__all__ = ["JsProxy", "JsException", "create_proxy", "create_once_callable", "to_js"]
