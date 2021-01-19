from ._core import JsException  # type: ignore

import traceback


def format_error(e, cur_tb=""):
    from pyodide_js._module import formatError

    if isinstance(e, JsException):
        if not cur_tb:
            cur_tb += "Traceback (most recent call last):\n"
        cur_tb += "".join(traceback.format_tb(e.__traceback__))
        cur_tb = formatError(e.js_error, cur_tb)
    else:
        tb = traceback.format_exception(type(e), e, e.__traceback__, chain=False)
        if cur_tb and tb[0].startswith("Traceback"):
            tb = tb[1:]
        cur_tb += "".join(tb)
    if e.__cause__ is not None:
        cause_format = format_error(e.__cause__)
        cur_tb = cause_format + traceback._cause_message + cur_tb
    elif e.__context__ is not None and not e.__suppress_context__:
        context_format = format_error(e.__context__)
        cur_tb = context_format + traceback._context_message + cur_tb
    return cur_tb
