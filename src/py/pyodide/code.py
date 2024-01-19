from functools import lru_cache
from typing import Any

from _pyodide._base import (
    CodeRunner,
    eval_code,
    eval_code_async,
    find_imports,
    should_quiet,
)


def run_js(code: str, /) -> Any:
    """
    A wrapper for the :js:func:`eval` function.

    Runs ``code`` as a Javascript code string and returns the result. Unlike
    :js:func:`eval`, if ``code`` is not a string we raise a :py:exc:`TypeError`.
    """
    from js import eval as eval_

    if not isinstance(code, str):
        raise TypeError(
            f"argument should have type 'string' not type '{type(code).__name__}'"
        )
    return eval_(code)


@lru_cache
def _relaxed_call_sig(func):
    from inspect import Parameter, signature

    try:
        sig = signature(func)
    except (TypeError, ValueError):
        return None
    new_params = list(sig.parameters.values())
    idx: int | None = -1
    for idx, param in enumerate(new_params):
        if param.kind in (Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD):
            break
        if param.kind == Parameter.VAR_POSITIONAL:
            idx = None
            break
    else:
        idx += 1
    if idx is not None:
        new_params.insert(idx, Parameter("__var_positional", Parameter.VAR_POSITIONAL))

    for param in new_params:
        if param.kind == Parameter.KEYWORD_ONLY:
            break
    else:
        new_params.append(Parameter("__var_keyword", Parameter.VAR_KEYWORD))
    new_sig = sig.replace(parameters=new_params)
    return new_sig


def relaxed_call(func, *args, **kwargs):
    """Call the function ignoring extra arguments

    If extra positional or keyword arguments are provided they will be
    discarded.
    """
    sig = _relaxed_call_sig(func)
    if sig is None:
        func(*args, **kwargs)
    bound = sig.bind(*args, **kwargs)
    bound.arguments.pop("__var_positional", None)
    bound.arguments.pop("__var_keyword", None)
    return func(*bound.args, **bound.kwargs)


__all__ = [
    "CodeRunner",
    "eval_code",
    "eval_code_async",
    "find_imports",
    "should_quiet",
    "run_js",
    "relaxed_call",
]
