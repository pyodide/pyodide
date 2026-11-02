"""Helpers for error_handling.c"""

import io
import sys
import traceback


def format_exception_for_js(exc: BaseException) -> str | None:
    """Do what PyErr_Print() does for ``exc``, but return the output of
    ``sys.excepthook`` instead of writing it to stderr.

    See: https://github.com/python/cpython/blob/67683da0ec8368c302569ff87af30fa1da2f873b/Python/pythonrun.c#L705
    """

    hook = getattr(sys, "excepthook", None)
    # If a user switched `sys.excepthook`, we can't use it to format the exception
    # because it might not be compatible with the default exception hook.
    # So just return None and let the caller fall back to the default error formatting.
    if hook is not traceback.print_exception or isinstance(exc, SystemExit):
        return None
    tb = exc.__traceback__
    # Same as PyErr_Print()
    sys.last_exc = exc
    sys.last_type = type(exc)
    sys.last_value = exc
    sys.last_traceback = tb
    try:
        sys.audit("sys.excepthook", hook, type(exc), exc, tb)
    except RuntimeError:
        # PyErr_Print() doesn't call the hook in this case
        return ""
    file = io.StringIO()
    hook(type(exc), exc, tb, file=file)
    return file.getvalue()
