"""
A library of helper utilities for connecting Python to the browser environment.
"""

import ast
from io import StringIO
from textwrap import dedent
from typing import Dict, List, Optional, Any


# Used in JsProxy
class JsException(BaseException):
    def __init__(self, js_error, *args):
        print("Calling JsException constructor", js_error, args)
        self.js_error = js_error
        

__version__ = "0.15.0"


def open_url(url: str) -> StringIO:
    """
    Fetches a given URL

    Parameters
    ----------
    url
       URL to fetch

    Returns
    -------
    a io.StringIO object with the contents of the URL.
    """
    from js import XMLHttpRequest

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send(None)
    return StringIO(req.response)


def eval_code(code: str, ns: Dict[str, Any]) -> None:
    """Runs a code string

    The last part of the provided code may be an expression.

    Parameters
    ----------
    code
       the Python code to run.
    ns
       `locals()` or `globals()` context where to execute code.

    Returns
    -------
    None
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    if len(mod.body) == 0:
        return None

    expr: Any
    if isinstance(mod.body[-1], ast.Expr):
        expr = ast.Expression(mod.body[-1].value)
        del mod.body[-1]
    else:
        expr = None

    if len(mod.body):
        exec(compile(mod, "<exec>", mode="exec"), ns, ns)
    if expr is not None:
        return eval(compile(expr, "<eval>", mode="eval"), ns, ns)
    else:
        return None


def find_imports(code: str) -> List[str]:
    """
    Finds the imports in a string of code

    Parameters
    ----------
    code
       the Python code to run.

    Returns
    -------
    A list of module names that are imported in the code.

    Examples
    --------
    >>> from pyodide import find_imports
    >>> code = "import numpy as np; import scipy.stats"
    >>> find_imports(code)
    ['numpy', 'scipy']
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    imports = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            for name in node.names:
                node_name = name.name
                imports.add(node_name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name is None:
                continue
            imports.add(module_name.split(".")[0])
    return list(sorted(imports))


def as_nested_list(obj) -> List:
    """Convert a nested JS array to nested Python list.

    Assumes a Javascript object is made of (possibly nested) arrays and
    converts them to nested Python lists.

    Parameters
    ----------
    obj
       a Javscript object made of nested arrays.

    Returns
    -------
    Python list, or a nested Python list
    """
    try:
        it = iter(obj)
        return [as_nested_list(x) for x in it]
    except TypeError:
        return obj


def get_completions(
    code: str, cursor: Optional[int] = None, namespaces: Optional[List] = None
) -> List[str]:
    """
    Get code autocompletion candidates

    Note that this function requires to have the jedi module loaded.

    Parameters
    ----------
    code
       the Python code to complete.
    cursor
       optional position in the code at which to autocomplete
    namespaces
       a list of namespaces

    Returns
    -------
    a list of autocompleted modules
    """
    import jedi
    import __main__

    if namespaces is None:
        namespaces = [__main__.__dict__]

    if cursor is None:
        cursor = len(code)
    code = code[:cursor]
    interp = jedi.Interpreter(code, namespaces)
    completions = interp.completions()

    return [x.name for x in completions]


__all__ = ["open_url", "eval_code", "find_imports", "as_nested_list", "get_completions"]
