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
    # PyErr_Print() calls sys.excepthook(type, value, traceback), which writes
    # to sys.stderr: the default hook sys.__excepthook__ takes no file
    # argument. We set sys.excepthook to traceback.print_exception (see
    # set_excepthook()), which also takes a file argument, so we can make it
    # write to a StringIO. A hook set by the user may not take a file argument,
    # so we return None to let the caller fall back to PyErr_Print().
    if hook is not traceback.print_exception:
        return None
    # If the inspect flag isn't set, PyErr_Print() exits for SystemExit. We set
    # it except in the CLI runner, where sys.exit() should exit.
    if isinstance(exc, SystemExit) and not sys.flags.inspect:
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
    traceback.print_exception(type(exc), exc, tb, file=file)
    return file.getvalue()
