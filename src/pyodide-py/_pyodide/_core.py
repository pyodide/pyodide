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
        A wrapper around a Javascript ``Error`` to allow the ``Error`` to be thrown in Python.
        """

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

        def to_py(self) -> Any:
            """Convert the :class:`JsProxy` to a native Python object as best as possible"""
            pass

        def then(self, onfulfilled: Callable, onrejected: Callable) -> "Promise":
            """The ``Promise.then`` api, wrapped to manage the lifetimes of the
            handlers.

            Only available if the wrapped Javascript object has a "then" method.
            Pyodide will automatically release the references to the handlers
            when the promise resolves.
            """

        def catch(self, onrejected: Callable) -> "Promise":
            """The ``Promise.catch`` api, wrapped to manage the lifetimes of the
            handler.

            Only available if the wrapped Javascript object has a "then" method.
            Pyodide will automatically release the references to the handler
            when the promise resolves.
            """

        def finally_(self, onfinally: Callable) -> "Promise":
            """The ``Promise.finally`` api, wrapped to manage the lifetimes of
            the handler.

            Only available if the wrapped Javascript object has a "then" method.
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


finally:
    __name__ = _save_name
    del _save_name
