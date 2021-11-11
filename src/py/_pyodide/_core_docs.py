from typing import Any, Callable, Iterable
from io import IOBase

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
    A wrapper around a JavaScript Error to allow it to be thrown in Python.
    See :ref:`type-translations-errors`.
    """

    @property
    def js_error(self) -> "JsProxy":
        """The original JavaScript error"""
        return JsProxy()


class ConversionError(Exception):
    """An error thrown when conversion between JavaScript and Python fails."""


class JsProxy:
    """A proxy to make a JavaScript object behave like a Python object

    For more information see the :ref:`type-translations` documentation. In
    particular, see
    :ref:`the list of __dunder__ methods <type-translations-jsproxy>`
    that are (conditionally) implemented on :any:`JsProxy`.
    """

    def object_entries(self) -> "JsProxy":
        "The JavaScript API ``Object.entries(object)``"

    def object_keys(self) -> "JsProxy":
        "The JavaScript API ``Object.keys(object)``"

    def object_values(self) -> "JsProxy":
        "The JavaScript API ``Object.values(object)``"

    def new(self, *args, **kwargs) -> "JsProxy":
        """Construct a new instance of the JavaScript object"""

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

        Present only if the wrapped JavaScript object has a "then" method.
        Pyodide will automatically release the references to the handlers
        when the promise resolves.
        """

    def catch(self, onrejected: Callable) -> "Promise":
        """The ``Promise.catch`` API, wrapped to manage the lifetimes of the
        handler.

        Present only if the wrapped JavaScript object has a "then" method.
        Pyodide will automatically release the references to the handler
        when the promise resolves.
        """

    def finally_(self, onfinally: Callable) -> "Promise":
        """The ``Promise.finally`` API, wrapped to manage the lifetimes of
        the handler.

        Present only if the wrapped JavaScript object has a "then" method.
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
        """Assign from a Python buffer into the JavaScript buffer.

        Present only if the wrapped JavaScript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign_to(self, to: Any):
        """Assign to a Python buffer from the JavaScript buffer.

        Present only if the wrapped JavaScript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_memoryview(self) -> memoryview:
        """Convert the buffer to a memoryview.

        Copies the data once. This currently has the same effect as :any:`to_py`.
        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_bytes(self) -> bytes:
        """Convert the buffer to a bytes object.

        Copies the data once.
        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_file(self, file: IOBase):
        """Writes the entire buffer to a file.

        Will write the entire contents of the buffer to the current position of
        the file.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.
        """

    def from_file(self, file: IOBase):
        """Reads from a file into the buffer.

        Will try to read a chunk of data of size the length of the buffer from
        the current position of the file.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.
        """

    def _into_file(self, file: IOBase):
        """Will write the entire contents of the buffer to the current position
        of the file using ``canOwn : true``. If the file is in the
        memfs, the data does not need to be copied. After this, the buffer
        cannot be used again.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.
        """

    def to_string(self, encoding=None) -> str:
        """Convert the buffer to a string object.

        Copies the data twice.

        The encoding argument will be passed to the Javascript
        [``TextDecoder``](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder)
        constructor. It should be one of the encodings listed in the table here:
        `https://encoding.spec.whatwg.org/#names-and-labels`. The default
        encoding is utf8.

        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """


# from pyproxy.c


def create_once_callable(obj: Callable) -> JsProxy:
    """Wrap a Python callable in a JavaScript function that can be called once.

    After being called the proxy will decrement the reference count
    of the Callable. The JavaScript function also has a ``destroy`` API that
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
    """Convert the object to JavaScript.

    This is similar to :any:`PyProxy.toJs`, but for use from Python. If the
    object would be implicitly translated to JavaScript, it will be returned
    unchanged. If the object cannot be converted into JavaScript, this
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
        Should be a JavaScript ``Array``. If provided, any ``PyProxies`` generated
        will be stored here. You can later use :any:`destroy_proxies` if you want
        to destroy the proxies from Python (or from JavaScript you can just iterate
        over the ``Array`` and destroy the proxies).

    create_pyproxies: bool, default=True
        If you set this to False, :any:`to_js` will raise an error

    dict_converter: Callable[[Iterable[JsProxy]], JsProxy], defauilt = None
        This converter if provided recieves a (JavaScript) iterable of
        (JavaScript) pairs [key, value]. It is expected to return the
        desired result of the dict conversion. Some suggested values for
        this argument:

            js.Map.new -- similar to the default behavior
            js.Array.from -- convert to an array of entries
            js.Object.fromEntries -- convert to a JavaScript object
    """
    return obj


class Promise(JsProxy):
    pass


def destroy_proxies(pyproxies: JsProxy):
    """Destroy all PyProxies in a JavaScript array.

    pyproxies must be a JsProxy of type PyProxy[]. Intended for use with the
    arrays created from the "pyproxies" argument of :any:`PyProxy.toJs` and
    :any:`to_js`. This method is necessary because indexing the Array from
    Python automatically unwraps the PyProxy into the wrapped Python object.
    """
    pass


__name__ = _save_name
del _save_name
