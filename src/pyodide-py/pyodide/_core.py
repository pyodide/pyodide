import platform

if platform.system() == "Emscripten":
    from _core import JsProxy, JsBoundMethod, JsException

else:
    # Can add shims here if we are so inclined.
    class JsException(Exception):
        """
        A wrapper around a Javascript Error to allow the Error to be thrown in Python.
        """

    class JsProxy:
        """A proxy to make a Javascript object behave like a Python object"""

    class JsProxy:
        """A proxy to make it possible to call Javascript bound methods from Python."""
