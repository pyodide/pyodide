import sys

if "_pyodide_core" not in sys.modules:
    from _pyodide import _core as _pyodide_core

    sys.modules["_pyodide_core"] = _pyodide_core

from _pyodide_core import JsProxy, JsException, create_proxy, create_once_callable

__all__ = ["JsProxy", "JsException", "create_proxy", "create_once_callable"]
