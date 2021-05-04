from ._base import open_url, eval_code, eval_code_async, find_imports
from ._core import JsProxy, JsException, create_once_callable, create_proxy, to_js  # type: ignore
from ._importhooks import jsfinder
from .webloop import WebLoopPolicy
from . import _state  # type: ignore # noqa
import asyncio
import sys
import platform

sys.meta_path.append(jsfinder)  # type: ignore
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module

if platform.system() == "Emscripten":
    asyncio.set_event_loop_policy(WebLoopPolicy())


__version__ = "0.18.0dev0"

__all__ = [
    "open_url",
    "eval_code",
    "eval_code_async",
    "find_imports",
    "JsProxy",
    "JsException",
    "to_js",
    "register_js_module",
    "unregister_js_module",
    "create_once_callable",
    "create_proxy",
]
