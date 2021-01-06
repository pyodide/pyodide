from ._base import open_url, eval_code, find_imports, as_nested_list, JsException
from .console import get_completions
from ._importhooks import JsImporter, register_js_module, unregister_js_module
import sys

import platform

if platform.system() == "Emscripten":
    sys.meta_path.append(JsImporter)  # type: ignore


__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "get_completions",
    "JsException",
    "register_js_module",
    "unregister_js_module",
]
