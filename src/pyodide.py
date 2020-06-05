"""
A library of helper utilities for connecting Python to the browser environment.
"""

import ast
import io
from textwrap import dedent


__version__ = '0.15.0'


def open_url(url):
    """
    Fetches a given *url* and returns a io.StringIO to access its contents.
    """
    from js import XMLHttpRequest

    req = XMLHttpRequest.new()
    req.open('GET', url, False)
    req.send(None)
    return io.StringIO(req.response)


def eval_code(code, ns):
    """
    Runs a string of code, the last part of which may be an expression.
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    if len(mod.body) == 0:
        return None

    if isinstance(mod.body[-1], ast.Expr):
        expr = ast.Expression(mod.body[-1].value)
        del mod.body[-1]
    else:
        expr = None

    if len(mod.body):
        exec(compile(mod, '<exec>', mode='exec'), ns, ns)
    if expr is not None:
        return eval(compile(expr, '<eval>', mode='eval'), ns, ns)
    else:
        return None


def find_imports(code):
    """
    Finds the imports in a string of code and returns a list of their package
    names.
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    imports = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            for name in node.names:
                name = name.name
                imports.add(name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            name = node.module
            imports.add(name.split('.')[0])
    return list(imports)


def as_nested_list(obj):
    """
    Assumes a Javascript object is made of (possibly nested) arrays and
    converts them to nested Python lists.
    """
    try:
        it = iter(obj)
        return [as_nested_list(x) for x in it]
    except TypeError:
        return obj


def get_completions(code, cursor=None, namespaces=None):
    """
    Get code autocompletion candidates.
    """
    import jedi
    import __main__

    if namespaces is None:
        namespaces = [__main__.__dict__]

    if cursor is None:
        cursor = len(code)
    code = code[:cursor]
    interp = jedi.Interpreter(source=code, namespaces=namespaces)
    completions = interp.completions()

    return [x.name for x in completions]


__all__ = [
    'open_url',
    'eval_code',
    'find_imports',
    'as_nested_list',
    'get_completions'
]
