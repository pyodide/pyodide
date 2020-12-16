"""
A library of helper utilities for connecting Python to the browser environment.
"""

import ast
from copy import deepcopy
from io import StringIO
from textwrap import dedent
from typing import Dict, List, Optional, Any, Tuple


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


COMPILE_FLAGS = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT  # type: ignore


def eval_code(code: str, ns: Dict[str, Any]) -> None:
    """Runs a code string.

    Parameters
    ----------
    code
       the Python code to run.
    ns
       `locals()` or `globals()` context where to execute code.

    Returns
    -------
    If the last nonwhitespace character of code is a semicolon return `None`.
    If the last statement is an expression, return the result of the
    expression. If the last statement is an assignment, we return the result
    of the assignment (including for destructuring assignments).
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    if len(mod.body) == 0:
        return None

    target_name = "<EXEC-LAST-EXPRESSION>"
    mod = _adjust_ast_to_store_result(target_name, mod, code)
    # res =
    eval(compile(mod, "<exec>", mode="exec", flags=COMPILE_FLAGS), ns, ns)
    # if iscoroutine(res):
    #     await res
    return ns.pop(target_name)


def _adjust_ast_to_store_result(
    target_name: str, tree: ast.Module, code: str
) -> ast.Module:
    """Add instruction to store result of expression into a variable with
    name "target_name"
    """
    target = [ast.Name(target_name, ctx=ast.Store())]
    [tree, result] = _adjust_ast_to_store_result_helper(tree, code)
    tree.body.append(ast.Assign(target, result))
    ast.fix_missing_locations(tree)
    return tree


def _adjust_ast_to_store_result_helper(
    tree: ast.Module, code: str
) -> Tuple[ast.Module, ast.expr]:
    # If the source ends in a semicolon, supress the result.
    if code.strip()[-1] == ";":
        return (tree, ast.Constant(None, None))  # type: ignore

    # We directly wrap Expr or Await node in an Assign node.
    last_node = tree.body[-1]
    if isinstance(last_node, (ast.Expr, ast.Await)):
        tree.body.pop()
        return (tree, last_node.value)

    # If node is already an Assign, deep copy the lvalue of the Assign and
    # store that structure into our result
    # This has the consequence that "[a, b] = (1,2)" returns "[1, 2]",
    # while "a, b = (1,2)" returns "(1,2)". This could be mildly unexpected
    # behavior but it seems entirely harmless.
    # Also in case of l[5] = 7 evaluates l[5] at the end. Python lvalues
    # can be pretty complicated.
    if isinstance(last_node, ast.Assign):
        target = last_node.targets[0]
        expr = deepcopy(target)
        # The deep copied expression was an lvalue but we are trying
        # to use it as an rvalue.
        # Need to replace all the "Store" lvalue context markers
        # with "Load" rvalue context markers.
        for x in ast.walk(expr):
            if hasattr(x, "ctx"):
                x.ctx = ast.Load()  # type: ignore
        return (tree, expr)
    # Remaining ast Nodes have no return value
    # (not sure what other possibilities there are actually...)
    return (tree, ast.Constant(None, None))  # type: ignore


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
