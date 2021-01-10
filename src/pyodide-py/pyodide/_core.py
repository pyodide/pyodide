# type: ignore
import platform

if platform.system() == "Emscripten":
    from _pyodide_core import JsProxy, JsBoundMethod, JsException
else:
    # Can add shims here if we are so inclined.
    class JsException(Exception):
        """
        A wrapper around a Javascript Error to allow the Error to be thrown in Python.
        """

        # Defined in jsproxy.c

    class JsProxy:
        """A proxy to make a Javascript object behave like a Python object"""

        # Defined in jsproxy.c

    class JsBoundMethod:
        """A proxy to make it possible to call Javascript bound methods from Python."""

        # Defined in jsproxy.c


__all__ = [JsProxy, JsBoundMethod, JsException]
