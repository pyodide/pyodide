from typing import Any, Callable, Iterable

# All docstrings for public `core` APIs should be extracted from here. We use
# the utilities in `docstring.py` and `docstring.c` to format them
# appropriately.

# Sphinx uses __name__ to determine the paths and such. It looks better for it
# to refer to e.g., `pyodide.JsProxy` than `_pyodide._core_docs.JsProxy`.
_save_name = __name__
__name__ = "pyodide"

# From jsproxy.c
class JsException(Exception):
    """
    A wrapper around a Javascript Error to allow it to be thrown in Python.
    See :ref:`type-translations-errors`.
    """

    @property
    def js_error(self) -> "JsProxy":
        """The original Javascript error"""
        return JsProxy()


class ConversionError(Exception):
    """An error thrown when conversion between Javascript and Python fails."""


class JsProxy:
    """A proxy to make a Javascript object behave like a Python object

    For more information see the :ref:`type-translations` documentation. In
    particular, see
    :ref:`the list of __dunder__ methods <type-translations-jsproxy>`
    that are (conditionally) implemented on :any:`JsProxy`.
    """

    def object_entries(self) -> "JsProxy":
        "The Javascript API ``Object.entries(object)``"

    def object_keys(self) -> "JsProxy":
        "The Javascript API ``Object.keys(object)``"

    def object_values(self) -> "JsProxy":
        "The Javascript API ``Object.values(object)``"

    def new(self, *args, **kwargs) -> "JsProxy":
        """Construct a new instance of the Javascript object"""

    def to_py(self, *, depth: int = -1) -> Any:
        """Convert the :class:`JsProxy` to a native Python object as best as
        possible.

        By default does a deep conversion, if a shallow conversion is
        desired, you can use ``proxy.to_py(depth=1)``. See
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

    # There are no types for buffers:
    # https://github.com/python/typing/issues/593
    # https://bugs.python.org/issue27501
    # This is just for docs so lets just make something up?

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign(self, rhs: Any):
        """Assign from a Python buffer into the Javascript buffer.

        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign_to(self, to: Any):
        """Assign to a Python buffer from the Javascript buffer.

        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """


# from pyproxy.c


def create_once_callable(obj: Callable) -> JsProxy:
    """Wrap a Python callable in a Javascript function that can be called once.

    After being called the proxy will decrement the reference count
    of the Callable. The Javascript function also has a ``destroy`` API that
    can be used to release the proxy without calling it.
    """
    return obj  # type: ignore


def create_proxy(obj: Any) -> JsProxy:
    """Create a ``JsProxy`` of a ``PyProxy``.

    This allows explicit control over the lifetime of the ``PyProxy`` from
    Python: call the ``destroy`` API when done.
    """
    return obj


# from python2js


def to_js(
    obj: Any,
    *,
    depth: int = -1,
    pyproxies: JsProxy = None,
    create_pyproxies: bool = True,
    dict_converter: Callable[[Iterable[JsProxy]], JsProxy] = None,
) -> JsProxy:
    """Convert the object to Javascript.

    This is similar to :any:`PyProxy.toJs`, but for use from Python. If the
    object would be implicitly translated to Javascript, it will be returned
    unchanged. If the object cannot be converted into Javascript, this
    method will return a :any:`JsProxy` of a :any:`PyProxy`, as if you had
    used :any:`pyodide.create_proxy`.

    See :ref:`type-translations-pyproxy-to-js` for more information.

    Parameters
    ----------
    obj : Any
        The Python object to convert

    depth : int, default=-1
        The maximum depth to do the conversion. Negative numbers are treated
        as infinite. Set this to 1 to do a shallow conversion.

    pyproxies: JsProxy, default = None
        Should be a Javascript ``Array``. If provided, any ``PyProxies`` generated
        will be stored here. You can later use :any:`destroy_proxies` if you want
        to destroy the proxies from Python (or from Javascript you can just iterate
        over the ``Array`` and destroy the proxies).

    create_pyproxies: bool, default=True
        If you set this to False, :any:`to_js` will raise an error

    dict_converter: Callable[[Iterable[JsProxy]], JsProxy], defauilt = None
        This converter if provided recieves a (Javascript) iterable of
        (Javascript) pairs [key, value]. It is expected to return the
        desired result of the dict conversion. Some suggested values for
        this argument:

            js.Map.new -- similar to the default behavior
            js.Array.from -- convert to an array of entries
            js.Object.fromEntries -- convert to a Javascript object
    """
    return obj


class Promise(JsProxy):
    pass


def destroy_proxies(pyproxies: JsProxy):
    """Destroy all PyProxies in a Javascript array.

    pyproxies must be a JsProxy of type PyProxy[]. Intended for use with the
    arrays created from the "pyproxies" argument of :any:`PyProxy.toJs` and
    :any:`to_js`. This method is necessary because indexing the Array from
    Python automatically unwraps the PyProxy into the wrapped Python object.
    """
    pass


__name__ = _save_name
del _save_name
