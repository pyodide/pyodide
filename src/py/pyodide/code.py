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


__all__ = [
    "CodeRunner",
    "eval_code",
    "eval_code_async",
    "find_imports",
    "should_quiet",
    "run_js",
]
