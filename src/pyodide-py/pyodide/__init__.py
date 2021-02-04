from ._base import open_url, eval_code, find_imports, as_nested_list
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
    # Start event loop running. This is so asyncio.create_task will work without
    # first calling asyncio.ensure_future, asyncio.get_event_loop, or manually
    # starting an event loop.
    asyncio.get_event_loop()


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
