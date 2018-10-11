"""
A library of helper utilities for connecting Python to the browser environment.
"""

import ast
import io

__version__ = '0.1.0'


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
    mod = ast.parse(code)
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


__all__ = ['open_url', 'eval_code', 'find_imports']
