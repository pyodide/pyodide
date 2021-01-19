from ._base import open_url, eval_code, find_imports, as_nested_list
from ._core import JsException  # type: ignore
from ._importhooks import JsFinder
import sys

jsfinder = JsFinder()
register_js_module = jsfinder.register_js_module
unregister_js_module = jsfinder.unregister_js_module
sys.meta_path.append(jsfinder)  # type: ignore


import traceback
_cause_message = (
    "\nThe above exception was the direct cause "
    "of the following exception:\n\n")

_context_message = (
    "\nDuring handling of the above exception, "
    "another exception occurred:\n\n")


def format_error(e, cur_tb=""):
    from pyodide_js._module import formatError
    if(isinstance(e, JsException)):
        if not cur_tb:
            cur_tb += "Traceback (most recent call last):\n" 
        cur_tb += "".join(traceback.format_tb(e.__traceback__))
        cur_tb = formatError(e.js_error, cur_tb)
    else:
        tb = traceback.format_exception(type(e), e, e.__traceback__, chain=False)
        if cur_tb and tb[0].startswith('Traceback'):
            tb = tb[1:]
        cur_tb += "".join(tb)
    if e.__cause__ is not None:
        cause_format = format_error(e.__cause__)
        cur_tb = cause_format + _cause_message + cur_tb
    elif (e.__context__ is not None and
        not e.__suppress_context__):
        context_format = format_error(e.__context__)
        cur_tb = context_format + _context_message + cur_tb
    return cur_tb

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
