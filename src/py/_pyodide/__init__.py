# _pyodide is imported at the very beginning of the initialization process so it
# cannot import from js, pyodide_js, or _pyodide_core. The one class here that
# does use such functions is JsFinder which requires access to
# _pyodide_core.JsProxy.
#
# register_js_finder is called from pyodide.js after _pyodide_core is completely
# initialized.
#
# All pure Python code that doesn't require imports from js, pyodide_js, or
# _pyodide_core belongs in _pyodide. Code that requires such imports belongs in
# pyodide.
from . import _base
from . import _importhook

__all__ = ["_base", "_importhook"]
