import platform
from typing import Any, Callable

if platform.system() == "Emscripten":
    from _pyodide_core import (
        JsProxy,
        JsException,
        JsBuffer,
        create_proxy,
        create_once_proxy,
    )
else:
    # Can add shims here if we are so inclined.
    class JsException(Exception):  # type: ignore
        """
        A wrapper around a Javascript Error to allow the Error to be thrown in Python.
        """

        # Defined in jsproxy.c

    class JsProxy:  # type: ignore
        """A proxy to make a Javascript object behave like a Python object"""

        # Defined in jsproxy.c

        # Defined in jsproxy.c

    def create_once_proxy(obj: Callable) -> JsProxy:
        """Wrap a Python callable in a Javascript function that can be called
        once. After being called the proxy will decrement the reference count
        of the Callable. The javascript function also has a `destroy` API that
        can be used to release the proxy without calling it.
        """
        return obj

    def create_proxy(obj: Any) -> JsProxy:
        """Create a PyProxy """
        return obj


__all__ = ["JsProxy", "JsException"]
