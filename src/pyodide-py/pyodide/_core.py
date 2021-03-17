import platform

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

    def create_once_proxy(obj):
        return obj

    def create_proxy(obj):
        return obj


__all__ = ["JsProxy", "JsException"]
