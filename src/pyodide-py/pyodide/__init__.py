from ._base import open_url, eval_code, find_imports, as_nested_list, JsException
from . import _importhooks
from .console import get_completions

# "Use" _importhooks to disable mypy unused import error,
# we need to execute _importhooks.
_importhooks = _importhooks

__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "get_completions",
    "JsException",
]
