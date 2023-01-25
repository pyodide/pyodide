from functools import update_wrapper
from textwrap import dedent
from typing import Any


def delete_attrs(cls):
    """Prevent attributes of a class or module from being documented.

    The top level documentation comment of the class or module will still be
    rendered.
    """
    for name in dir(cls):
        if not name.startswith("_"):
            try:
                delattr(cls, name)
            except Exception:
                pass


def docs_argspec(argspec: str) -> Any:
    """Decorator to override the argument spec of the function that is
    rendered in the docs.

    If the documentation finds a __wrapped__ attribute, it will use that to
    render the argspec instead of the function itself. Assign an appropriate
    fake function to __wrapped__ with the desired argspec.
    """

    def dec(func):
        d = func.__globals__
        TEMP_NAME = "_xxxffff___"
        assert TEMP_NAME not in d
        code = dedent(
            f"""\
            def {TEMP_NAME}{argspec}:
                pass
            """
        )
        # exec in func.__globals__ context so that type hints don't case NameErrors.
        exec(code, d)
        f = d.pop(TEMP_NAME)

        # # Run update_wrapper but keep f's annotations and don't set
        # # f.__wrapped__ (would cause an infinite loop!)
        annotations = f.__annotations__
        update_wrapper(f, func)
        f.__annotations__ = annotations
        del f.__wrapped__

        # Set wrapper to be our fake function
        func.__wrapped__ = f

        return func

    return dec
