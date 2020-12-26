from ._base import open_url, eval_code, find_imports, as_nested_list, JsException
from .console import get_completions
from .webloop import WebLoop, WebLoopPolicy

import asyncio

asyncio.set_event_loop_policy(WebLoopPolicy())

__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "get_completions",
    "JsException",
    "WebLoop",
    "WebLoopPolicy",
]
