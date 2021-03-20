from ._base import open_url, eval_code, eval_code_async, find_imports, as_nested_list
from ._core import JsException, create_once_callable, create_proxy  # type: ignore
from ._importhooks import jsfinder
from . import _state # type: ignore # noqa
from .webloop import WebLoopPolicy
import asyncio
import sys
import platform

sys.meta_path.append(jsfinder)  # type: ignore
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module

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
    "create_once_callable",
    "create_proxy",
]
