from typing import Any, Callable

from js import clearInterval, clearTimeout, setInterval, setTimeout
from pyodide import create_once_callable, JsProxy, create_proxy


class Destroyable:
    def destroy(self):
        pass


EVENT_LISTENERS: dict[tuple[JsProxy, str, JsProxy], JsProxy] = {}


def add_event_listener(elt: JsProxy, event: str, listener: Callable[[Any], None]):
    proxy = create_proxy(listener)
    EVENT_LISTENERS[(id(elt), event, listener)] = proxy
    elt.addEventListener(event, proxy)


def remove_event_listener(elt: JsProxy, event: str, listener: Callable[[Any], None]):
    proxy = EVENT_LISTENERS[(id(elt), event, listener)]
    elt.removeEventListener(event, proxy)
    proxy.destroy()


TIMEOUTS: dict[int, Destroyable] = {}


def set_timeout(callback: Callable[[], None], timeout: int) -> int:
    id = -1

    def wrapper():
        nonlocal id
        callback()
        TIMEOUTS.pop(id, None)

    callable = create_once_callable(wrapper)
    id = setTimeout(callable, timeout)
    TIMEOUTS[id] = callable
    return id


# An object with a no-op destroy method so we can do
#
# TIMEOUTS.pop(id, DUMMY_DESTROYABLE).destroy()
#
# and either it gets a real object and calls the real destroy method or it gets
# the fake which does nothing. This is to handle the case where clear_timeout is
# called after the timeout executes.
DUMMY_DESTROYABLE = Destroyable()


def clear_timeout(id: int):
    clearTimeout(id)
    TIMEOUTS.pop(id, DUMMY_DESTROYABLE).destroy()


def set_interval(callback: Callable[[], None], interval: int) -> int:
    id = -1

    def wrapper():
        nonlocal id
        callback()
        TIMEOUTS.pop(id, None)

    callable = create_once_callable(wrapper)
    id = setInterval(callable, interval)
    TIMEOUTS[id] = callable
    return id


def clear_interval(id: int):
    clearInterval(id)
    TIMEOUTS.pop(id).destroy()
