import __main__
import sys
import gc

from ._core import JsProxy
from ._importhooks import jsfinder


def save_state():
    loaded_js_modules = {}
    for [key, value] in sys.modules.items():
        if isinstance(value, JsProxy):
            loaded_js_modules[key] = value

    return dict(
        globals=dict(__main__.__dict__),
        js_modules=dict(jsfinder.jsproxies),
        loaded_js_modules=loaded_js_modules,
    )


def restore_state(state):
    __main__.__dict__.clear()
    __main__.__dict__.update(state["globals"])

    jsfinder.jsproxies = state["js_modules"]
    loaded_js_modules = state["loaded_js_modules"]
    for [key, value] in list(sys.modules.items()):
        if isinstance(value, JsProxy) and key not in loaded_js_modules:
            del sys.modules[key]
    sys.modules.update(loaded_js_modules)

    sys.last_type = None
    sys.last_value = None
    sys.last_traceback = None

    return gc.collect(2)


__all__ = ["save_state", "restore_state"]
