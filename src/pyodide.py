"""
A library of helper utilities for connecting Python to the browser environment.
"""

from js import XMLHttpRequest

import ast
import io


def open_url(url):
    """
    Fetches a given *url* and returns a io.StringIO to access its contents.
    """
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


__all__ = ['open_url', 'eval_code']
