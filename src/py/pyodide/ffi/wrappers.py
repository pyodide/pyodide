from collections.abc import Callable
from typing import Any

from .._core import IN_BROWSER, JsProxy, create_once_callable, create_proxy

if IN_BROWSER:
    from js import clearInterval, clearTimeout, setInterval, setTimeout


class Destroyable:
    def destroy(self):
        pass


EVENT_LISTENERS: dict[tuple[int, str, Callable[[Any], None]], JsProxy] = {}


def add_event_listener(
    elt: JsProxy, event: str, listener: Callable[[Any], None]
) -> None:
    """Wrapper for JavaScript's addEventListener() which automatically manages the lifetime
    of a JsProxy corresponding to the listener param.
    """
    proxy = create_proxy(listener)
    EVENT_LISTENERS[(elt.js_id, event, listener)] = proxy
    elt.addEventListener(event, proxy)


def remove_event_listener(
    elt: JsProxy, event: str, listener: Callable[[Any], None]
) -> None:
    """Wrapper for JavaScript's removeEventListener() which automatically manages the lifetime
    of a JsProxy corresponding to the listener param.
    """
    proxy = EVENT_LISTENERS.pop((elt.js_id, event, listener))
    elt.removeEventListener(event, proxy)
    proxy.destroy()


TIMEOUTS: dict[int, Destroyable] = {}


def set_timeout(callback: Callable[[], None], timeout: int) -> int | JsProxy:
    """Wrapper for JavaScript's setTimeout() which automatically manages the lifetime
    of a JsProxy corresponding to the callback param.
    """
    id = -1

    def wrapper():
        nonlocal id
        callback()
        TIMEOUTS.pop(id, None)

    callable = create_once_callable(wrapper)
    timeout_retval: int | JsProxy = setTimeout(callable, timeout)
    id = timeout_retval if isinstance(timeout_retval, int) else timeout_retval.js_id
    TIMEOUTS[id] = callable
    return timeout_retval


# An object with a no-op destroy method so we can do
#
# TIMEOUTS.pop(id, DUMMY_DESTROYABLE).destroy()
#
# and either it gets a real object and calls the real destroy method or it gets
# the fake which does nothing. This is to handle the case where clear_timeout is
# called after the timeout executes.
DUMMY_DESTROYABLE = Destroyable()


def clear_timeout(timeout_retval: int | JsProxy) -> None:
    """Wrapper for JavaScript's clearTimeout() which automatically manages the lifetime
    of a JsProxy corresponding to the callback param.
    """
    clearTimeout(timeout_retval)
    id = timeout_retval if isinstance(timeout_retval, int) else timeout_retval.js_id
    TIMEOUTS.pop(id, DUMMY_DESTROYABLE).destroy()


INTERVAL_CALLBACKS: dict[int, Destroyable] = {}


def set_interval(callback: Callable[[], None], interval: int) -> int | JsProxy:
    """Wrapper for JavaScript's setInterval() which automatically manages the lifetime
    of a JsProxy corresponding to the callback param.
    """
    proxy = create_proxy(callback)
    interval_retval = setInterval(proxy, interval)
    id = interval_retval if isinstance(interval_retval, int) else interval_retval.js_id
    INTERVAL_CALLBACKS[id] = proxy
    return interval_retval


def clear_interval(interval_retval: int | JsProxy) -> None:
    """Wrapper for JavaScript's clearInterval() which automatically manages the lifetime
    of a JsProxy corresponding to the callback param.
    """
    clearInterval(interval_retval)
    id = interval_retval if isinstance(interval_retval, int) else interval_retval.js_id
    INTERVAL_CALLBACKS.pop(id, DUMMY_DESTROYABLE).destroy()
