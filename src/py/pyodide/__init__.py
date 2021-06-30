from ._core import JsProxy, JsException, create_once_callable, create_proxy, to_js  # type: ignore
from _pyodide._base import (
    eval_code,
    eval_code_async,
    find_imports,
    CodeRunner,
    should_quiet,
)
from ._util import open_url
from . import _util  # type: ignore # noqa
from .webloop import WebLoopPolicy

import asyncio
import platform

from _pyodide._importhook import jsfinder

register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module

if platform.system() == "Emscripten":
    asyncio.set_event_loop_policy(WebLoopPolicy())


__version__ = "0.18.0dev0"

__all__ = [
    "open_url",
    "eval_code",
    "eval_code_async",
    "CodeRunner",
    "find_imports",
    "JsProxy",
    "JsException",
    "to_js",
    "register_js_module",
    "unregister_js_module",
    "create_once_callable",
    "create_proxy",
    "should_quiet",
]
