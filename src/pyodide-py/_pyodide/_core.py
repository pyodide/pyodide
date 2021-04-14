# type: ignore

from typing import Any, Callable

# All docstrings for public `core` APIs should be extracted from here. We use
# the utilities in `docstring.py` and `docstring.c` to format them
# appropriately.

# Sphinx uses __name__ to determine the paths and such. It looks better for it
# to refer to e.g., `pyodide.JsProxy` than `_pyodide._core.JsProxy`.
_save_name = __name__
__name__ = "pyodide"
try:
    # From jsproxy.c

    class JsException(Exception):
        """
        A wrapper around a Javascript Error to allow it to be thrown in Python.
        See :ref:`type-translations-errors`.
        """

        @property
        def js_error(self):
            """The original Javascript error"""

    class JsProxy:
        """A proxy to make a Javascript object behave like a Python object

        For more information see :ref:`type-translations` documentation.
        """

        def __init__(self):
            """"""

        def object_entries(self) -> "JsProxy":
            "The Javascript API ``Object.entries(object)``"

        def object_keys(self) -> "JsProxy":
            "The Javascript API ``Object.keys(object)``"

        def object_values(self) -> "JsProxy":
            "The Javascript API ``Object.values(object)``"

        def new(self, *args, **kwargs) -> "JsProxy":
            """Construct a new instance of the Javascript object"""

        def to_py(self, depth: int = -1) -> Any:
            """Convert the :class:`JsProxy` to a native Python object as best as
            possible.

            By default does a deep conversion, if a shallow conversion is
            desired, you can use ``proxy.to_py(1)``. See
            :ref:`type-translations-jsproxy-to-py` for more information.
            """
            pass

        def then(self, onfulfilled: Callable, onrejected: Callable) -> "Promise":
            """The ``Promise.then`` API, wrapped to manage the lifetimes of the
            handlers.

            Present only if the wrapped Javascript object has a "then" method.
            Pyodide will automatically release the references to the handlers
            when the promise resolves.
            """

        def catch(self, onrejected: Callable) -> "Promise":
            """The ``Promise.catch`` API, wrapped to manage the lifetimes of the
            handler.

            Present only if the wrapped Javascript object has a "then" method.
            Pyodide will automatically release the references to the handler
            when the promise resolves.
            """

        def finally_(self, onfinally: Callable) -> "Promise":
            """The ``Promise.finally`` API, wrapped to manage the lifetimes of
            the handler.

            Present only if the wrapped Javascript object has a "then" method.
            Pyodide will automatically release the references to the handler
            when the promise resolves. Note the trailing underscore in the name;
            this is needed because ``finally`` is a reserved keyword in Python.
            """

    # from pyproxy.c

    def create_once_callable(obj: Callable) -> JsProxy:
        """Wrap a Python callable in a Javascript function that can be called once.

        After being called the proxy will decrement the reference count
        of the Callable. The Javascript function also has a ``destroy`` API that
        can be used to release the proxy without calling it.
        """
        return obj

    def create_proxy(obj: Any) -> JsProxy:
        """Create a ``JsProxy`` of a ``PyProxy``.

        This allows explicit control over the lifetime of the ``PyProxy`` from
        Python: call the ``destroy`` API when done.
        """
        return obj

    # from python2js

    def to_js(obj: Any, depth: int = -1) -> JsProxy:
        """Convert the object to Javascript.

        This is similar to :any:`PyProxy.toJs`, but for use from Python. If the
        object would be implicitly translated to Javascript, it will be returned
        unchanged. If the object cannot be converted into Javascript, this
        method will return a :any:`JsProxy` of a :any:`PyProxy`, as if you had
        used :any:`pyodide.create_proxy`.

        See :ref:`type-translations-pyproxy-to-js` for more information.
        """
        return obj


finally:
    __name__ = _save_name
    del _save_name
