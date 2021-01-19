from ._base import open_url, eval_code, find_imports, as_nested_list
from ._core import JsException  # type: ignore
from ._importhooks import JsFinder
from .traceback import format_error
import sys

jsfinder = JsFinder()
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module
sys.meta_path.append(jsfinder)  # type: ignore


__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "JsException",
    "register_js_module",
    "unregister_js_module",
    "format_error",
]
