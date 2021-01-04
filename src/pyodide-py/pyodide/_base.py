"""
A library of helper utilities for connecting Python to the browser environment.
"""
# Added by C:
# JsException (from jsproxy.c)

import ast
from asyncio import iscoroutine
from io import StringIO
from textwrap import dedent
from typing import Dict, List, Any
import tokenize


class JsException(Exception):
    """
    A wrapper around a Javascript Error to allow the Error to be thrown in Python.
    """

    # This gets overwritten in jsproxy.c, it is just here for autodoc and humans
    # reading this file.
    pass


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


def quiet_code(code: str) -> bool:
    """
    Does the last nonwhitespace character of code is a semicolon?

    This can be overridden to customize the way eval_code is silenced.

    Examples
    --------
    >>> quiet_code('x + 1')
    False
    >>> quiet_code('x + 1 ;')
    True
    >>> quiet_code('x + 1 # comment ;')
    False
    """
    # largely inspired from IPython:
    # https://github.com/ipython/ipython/blob/86d24741188b0cedd78ab080d498e775ed0e5272/IPython/core/displayhook.py#L84

    codeio = StringIO(code)
    tokens = list(tokenize.generate_tokens(codeio.readline))

    for token in reversed(tokens):
        if token.type in (
            tokenize.ENDMARKER,
            tokenize.NL,  # ignoring empty lines (\n\n)
            tokenize.NEWLINE,
            tokenize.COMMENT,
        ):
            continue
        return (token.type == tokenize.OP) and (token.string == ";")

    return False


def eval_code(code: str, ns: Dict[str, Any], compile_flags: int = 0) -> Any:
    """Runs a code string.

    Parameters
    ----------
    code
       the Python code to run.
    ns
       `locals()` or `globals()` context where to execute code.
    compile_flags
       AST compile flags.

    Returns
    -------
    If the last nonwhitespace character of code is a semicolon return `None`.
    If the last statement is an expression, return the
    result of the expression.
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    if len(mod.body) == 0:
        return None

    # we extract last expression
    last_expr = None
    if isinstance(mod.body[-1], (ast.Expr, ast.Await)) and not quiet_code(code):
        last_expr = ast.Expression(mod.body.pop().value)  # type: ignore

    # then run code
    if len(mod.body):
        exec(compile(mod, "<exec>", "exec", flags=compile_flags), ns, ns)
    if last_expr is not None:
        return eval(compile(last_expr, "<exec>", "eval", flags=compile_flags), ns, ns)


async def _eval_code_async(code: str, ns: Dict[str, Any]) -> Any:
    """ For use once we add an EventLoop. """
    res = eval_code(code, ns, compile_flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)  # type: ignore
    if iscoroutine(res):
        return await res
    else:
        return res


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
