from ._base import open_url, eval_code, eval_code_async, find_imports, as_nested_list
from ._core import JsException  # type: ignore
from ._importhooks import JsFinder
from .webloop import WebLoopPolicy
import asyncio
import sys
import platform

jsfinder = JsFinder()
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module
sys.meta_path.append(jsfinder)  # type: ignore

if platform.system() == "Emscripten":
    asyncio.set_event_loop_policy(WebLoopPolicy())


__version__ = "0.17.dev0"

__all__ = [
    "open_url",
    "eval_code",
    "eval_code_async",
    "find_imports",
    "as_nested_list",
    "JsException",
    "register_js_module",
    "unregister_js_module",
]
