from ._base import open_url, eval_code, find_imports, as_nested_list, JsException
from ._importhooks import _monkeypatch_path_importer_cache
from .console import get_completions

_monkeypatch_path_importer_cache()
del _monkeypatch_path_importer_cache

__version__ = "0.16.1"

__all__ = [
    "open_url",
    "eval_code",
    "find_imports",
    "as_nested_list",
    "get_completions",
    "JsException",
]
