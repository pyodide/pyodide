import sys
from collections.abc import Callable, Iterable, Iterator
from io import IOBase
from typing import Any

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

    @property
    def js_id(self) -> int:
        """An id number which can be used as a dictionary/set key if you want to
        key on JavaScript object identity.

        If two `JsProxy` are made with the same backing JavaScript object, they
        will have the same `js_id`. The reault is a "pseudorandom" 32 bit integer.
        """
        return 0

    @property
    def typeof(self) -> str:
        """Returns the JavaScript type of the JsProxy.

        Corresponds to `typeof obj;` in JavaScript. You may also be interested
        in the `constuctor` attribute which returns the type as an object.
        """
        return "object"

    def object_entries(self) -> "JsProxy":
        "The JavaScript API ``Object.entries(object)``"

    def object_keys(self) -> "JsProxy":
        "The JavaScript API ``Object.keys(object)``"

    def object_values(self) -> "JsProxy":
        "The JavaScript API ``Object.values(object)``"

    def new(self, *args: Any, **kwargs: Any) -> "JsProxy":
        """Construct a new instance of the JavaScript object"""

    def to_py(
        self,
        *,
        depth: int = -1,
        default_converter: Callable[
            ["JsProxy", Callable[["JsProxy"], Any], Callable[["JsProxy", Any], None]],
            Any,
        ]
        | None = None,
    ) -> Any:
        """Convert the :class:`JsProxy` to a native Python object as best as
        possible.

        By default, does a deep conversion, if a shallow conversion is desired,
        you can use ``proxy.to_py(depth=1)``. See
        :ref:`type-translations-jsproxy-to-py` for more information.

        ``default_converter`` if present will be invoked whenever Pyodide does
        not have some built in conversion for the object.
        If ``default_converter`` raises an error, the error will be allowed to
        propagate. Otherwise, the object returned will be used as the
        conversion. ``default_converter`` takes three arguments. The first
        argument is the value to be converted.

        Here are a couple examples of converter functions. In addition to the
        normal conversions, convert ``Date`` to ``datetime``:

        .. code-block:: python

            from datetime import datetime
            def default_converter(value, _ignored1, _ignored2):
                if value.constructor.name == "Date":
                    return datetime.fromtimestamp(d.valueOf()/1000)
                return value

        Don't create any JsProxies, require a complete conversion or raise an error:

        .. code-block:: python

            def default_converter(_value, _ignored1, _ignored2):
                raise Exception("Failed to completely convert object")

        The second and third arguments are only needed for converting
        containers. The second argument is a conversion function which is used
        to convert the elements of the container with the same settings. The
        third argument is a "cache" function which is needed to handle self
        referential containers. Consider the following example. Suppose we have
        a Javascript ``Pair`` class:

        .. code-block:: javascript

            class Pair {
                constructor(first, second){
                    this.first = first;
                    this.second = second;
                }
            }

        We can use the following ``default_converter`` to convert ``Pair`` to ``list``:

        .. code-block:: python

            def default_converter(value, convert, cache):
                if value.constructor.name != "Pair":
                    return value
                result = []
                cache(value, result);
                result.append(convert(value.first))
                result.append(convert(value.second))
                return result

        Note that we have to cache the conversion of ``value`` before converting
        ``value.first`` and ``value.second``. To see why, consider a self
        referential pair:

        .. code-block:: javascript

            let p = new Pair(0, 0);
            p.first = p;

        Without ``cache(value, result);``, converting ``p`` would lead to an
        infinite recurse. With it, we can successfully convert ``p`` to a list
        such that ``l[0] is l``.
        """
        pass

    def then(
        self, onfulfilled: Callable[[Any], Any], onrejected: Callable[[Any], Any]
    ) -> "Promise":
        """The ``Promise.then`` API, wrapped to manage the lifetimes of the
        handlers.

        Present only if the wrapped JavaScript object has a "then" method.
        Pyodide will automatically release the references to the handlers
        when the promise resolves.
        """

    def catch(self, onrejected: Callable[[Any], Any], /) -> "Promise":
        """The ``Promise.catch`` API, wrapped to manage the lifetimes of the
        handler.

        Present only if the wrapped JavaScript object has a "then" method.
        Pyodide will automatically release the references to the handler
        when the promise resolves.
        """

    def finally_(self, onfinally: Callable[[Any], Any], /) -> "Promise":
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
    def assign(self, rhs: Any, /) -> None:
        """Assign from a Python buffer into the JavaScript buffer.

        Present only if the wrapped JavaScript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign_to(self, to: Any, /) -> None:
        """Assign to a Python buffer from the JavaScript buffer.

        Present only if the wrapped JavaScript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_memoryview(self) -> memoryview:
        """Convert a buffer to a memoryview.

        Copies the data once. This currently has the same effect as :any:`to_py`.
        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_bytes(self) -> bytes:
        """Convert a buffer to a bytes object.

        Copies the data once.
        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def to_file(self, file: IOBase, /) -> None:
        """Writes a buffer to a file.

        Will write the entire contents of the buffer to the current position of
        the file.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.

        Example
        -------
        >>> import pytest; pytest.skip()
        >>> from js import Uint8Array
        >>> x = Uint8Array.new(range(10))
        >>> with open('file.bin', 'wb') as fh:
        ...    x.to_file(fh)
        which is equivalent to,
        >>> with open('file.bin', 'wb') as fh:
        ...    data = x.to_bytes()
        ...    fh.write(data)
        but the latter copies the data twice whereas the former only copies the
        data once.
        """

    def from_file(self, file: IOBase, /) -> None:
        """Reads from a file into a buffer.

        Will try to read a chunk of data the same size as the buffer from
        the current position of the file.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.

        Example
        -------
        >>> import pytest; pytest.skip()
        >>> from js import Uint8Array
        >>> # the JsProxy need to be pre-allocated
        >>> x = Uint8Array.new(range(10))
        >>> with open('file.bin', 'rb') as fh:
        ...    x.read_file(fh)
        which is equivalent to
        >>> x = Uint8Array.new(range(10))
        >>> with open('file.bin', 'rb') as fh:
        ...    chunk = fh.read(size=x.byteLength)
        ...    x.assign(chunk)
        but the latter copies the data twice whereas the former only copies the
        data once.
        """

    def _into_file(self, file: IOBase, /) -> None:
        """Will write the entire contents of a buffer into a file using
        ``canOwn : true`` without any copy. After this, the buffer cannot be
        used again.

        If ``file`` is not empty, its contents will be overwritten!

        Only ``MEMFS`` cares about the ``canOwn`` flag, other file systems will
        just ignore it.

        Present only if the wrapped Javascript object is an ArrayBuffer or an
        ArrayBuffer view.

        Example
        -------
        >>> import pytest; pytest.skip()
        >>> from js import Uint8Array
        >>> x = Uint8Array.new(range(10))
        >>> with open('file.bin', 'wb') as fh:
        ...    x._into_file(fh)
        which is similar to
        >>> with open('file.bin', 'wb') as fh:
        ...    data = x.to_bytes()
        ...    fh.write(data)
        but the latter copies the data once whereas the former doesn't copy the
        data.
        """

    def to_string(self, encoding: str | None = None) -> str:
        """Convert a buffer to a string object.

        Copies the data twice.

        The encoding argument will be passed to the Javascript
        [``TextDecoder``](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder)
        constructor. It should be one of the encodings listed in the table here:
        `https://encoding.spec.whatwg.org/#names-and-labels`. The default
        encoding is utf8.

        Present only if the wrapped Javascript object is an ArrayBuffer or
        an ArrayBuffer view.
        """

    def extend(self, other: Iterable[Any]) -> None:
        """Extend array by appending elements from the iterable.

        Present only if the wrapped Javascript object is an array.
        """

    def __reversed__(self) -> Iterator[Any]:
        """Return a reverse iterator over the Array.

        Present only if the wrapped Javascript object is an array.
        """

    def pop(self, /, index: int = -1) -> Any:
        """Remove and return item at index (default last).

        Raises IndexError if list is empty or index is out of range.
        Present only if the wrapped Javascript object is an array.
        """

    def append(self, /, object: Any) -> None:
        """Append object to the end of the list.

        Present only if the wrapped Javascript object is an array.
        """

    def index(self, /, value: Any, start: int = 0, stop: int = sys.maxsize) -> int:
        """Return first index of value.

        Present only if the wrapped Javascript object is an array.
        Raises ValueError if the value is not present.
        """

    def count(self, /, x: Any) -> int:
        """Return the number of times x appears in the list.

        Present only if the wrapped Javascript object is an array.
        """

    def reverse(self) -> None:
        """Reverse the array in place.

        Present only if the wrapped Javascript object is an array.
        """

    def unwrap(self) -> Any:
        """Unwrap a double proxy created with :any:`create_proxy` into the
        wrapped Python object.

        Only present on double proxies.
        """


# from pyproxy.c


def create_once_callable(obj: Callable[..., Any], /) -> JsProxy:
    """Wrap a Python callable in a JavaScript function that can be called once.

    After being called the proxy will decrement the reference count
    of the Callable. The JavaScript function also has a ``destroy`` API that
    can be used to release the proxy without calling it.
    """
    return obj  # type: ignore[return-value]


def create_proxy(
    obj: Any, /, *, capture_this: bool = False, roundtrip: bool = True
) -> JsProxy:
    """Create a ``JsProxy`` of a ``PyProxy``.

    This allows explicit control over the lifetime of the ``PyProxy`` from
    Python: call the ``destroy`` API when done.

    Parameters
    ----------
    obj: any
        The object to wrap.

    capture_this : bool, default=False
        If the object is callable, should `this` be passed as the first argument
        when calling it from JavaScript.

    roundtrip: bool, default=True
        When the proxy is converted back from JavaScript to Python, if this is
        ``True`` it is converted into a double proxy. If ``False``, it is
        unwrapped into a Python object. In the case that ``roundtrip`` is
        ``True`` it is possible to unwrap a double proxy with the :any:`unwrap`
        method. This is useful to allow easier control of lifetimes from Python:

        .. code-block:: python

            from js import o
            d = {}
            o.d = create_proxy(d, roundtrip=True)
            o.d.destroy() # Destroys the proxy created with create_proxy

        With ``roundtrip=False`` this would be an error.
    """
    return obj


# from python2js


def to_js(
    obj: Any,
    /,
    *,
    depth: int = -1,
    pyproxies: JsProxy | None = None,
    create_pyproxies: bool = True,
    dict_converter: Callable[[Iterable[JsProxy]], JsProxy] | None = None,
    default_converter: Callable[
        [Any, Callable[[Any], JsProxy], Callable[[Any, JsProxy], None]], JsProxy
    ]
    | None = None,
) -> JsProxy:
    """Convert the object to JavaScript.

    This is similar to :any:`PyProxy.toJs`, but for use from Python. If the
    object can be implicitly translated to JavaScript, it will be returned
    unchanged. If the object cannot be converted into JavaScript, this
    method will return a :any:`JsProxy` of a :any:`PyProxy`, as if you had
    used :any:`pyodide.ffi.create_proxy`.

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

    dict_converter: Callable[[Iterable[JsProxy]], JsProxy], default = None
        This converter if provided receives a (JavaScript) iterable of
        (JavaScript) pairs [key, value]. It is expected to return the
        desired result of the dict conversion. Some suggested values for
        this argument:

            js.Map.new -- similar to the default behavior
            js.Array.from -- convert to an array of entries
            js.Object.fromEntries -- convert to a JavaScript object
    default_converter: Callable[[Any, Callable[[Any], JsProxy], Callable[[Any, JsProxy], None]], JsProxy], default=None
        If present will be invoked whenever Pyodide does not have some built in
        conversion for the object. If ``default_converter`` raises an error, the
        error will be allowed to propagate. Otherwise, the object returned will
        be used as the conversion. ``default_converter`` takes three arguments.
        The first argument is the value to be converted.

        Here are a couple examples of converter functions. In addition to the
        normal conversions, convert ``Date`` to ``datetime``:

        .. code-block:: python

            from datetime import datetime
            from js import Date
            def default_converter(value, _ignored1, _ignored2):
                if isinstance(value, datetime):
                    return Date.new(value.timestamp() * 1000)
                return value

        Don't create any PyProxies, require a complete conversion or raise an error:

        .. code-block:: python

            def default_converter(_value, _ignored1, _ignored2):
                raise Exception("Failed to completely convert object")

        The second and third arguments are only needed for converting
        containers. The second argument is a conversion function which is used
        to convert the elements of the container with the same settings. The
        third argument is a "cache" function which is needed to handle self
        referential containers. Consider the following example. Suppose we have
        a Python ``Pair`` class:

        .. code-block:: python

            class Pair:
                def __init__(self, first, second):
                    self.first = first
                    self.second = second

        We can use the following ``default_converter`` to convert ``Pair`` to ``Array``:

        .. code-block:: python

            from js import Array
            def default_converter(value, convert, cache):
                if not isinstance(value, Pair):
                    return value
                result = Array.new()
                cache(value, result);
                result.push(convert(value.first))
                result.push(convert(value.second))
                return result

        Note that we have to cache the conversion of ``value`` before converting
        ``value.first`` and ``value.second``. To see why, consider a self
        referential pair:

        .. code-block:: javascript

            p = Pair(0, 0);
            p.first = p;

        Without ``cache(value, result);``, converting ``p`` would lead to an
        infinite recurse. With it, we can successfully convert ``p`` to an Array
        such that ``l[0] === l``.
    """
    return obj


class Promise(JsProxy):
    pass


def destroy_proxies(pyproxies: JsProxy, /) -> None:
    """Destroy all PyProxies in a JavaScript array.

    pyproxies must be a JsProxy of type PyProxy[]. Intended for use with the
    arrays created from the "pyproxies" argument of :any:`PyProxy.toJs` and
    :any:`to_js`. This method is necessary because indexing the Array from
    Python automatically unwraps the PyProxy into the wrapped Python object.
    """
    pass


__name__ = _save_name
del _save_name
