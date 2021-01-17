from ._base import open_url, eval_code, find_imports, as_nested_list
from ._core import JsException  # type: ignore
from ._importhooks import JsImporter

import platform
import sys

jsimporter = JsImporter()
register_js_module = jsimporter.register_js_module
unregister_js_module = jsimporter.unregister_js_module
sys.meta_path.append(jsimporter)  # type: ignore


__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "JsException",
    "register_js_module",
    "unregister_js_module",
]
