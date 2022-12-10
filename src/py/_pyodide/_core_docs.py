import sys
from collections.abc import (
    AsyncIterator,
    Callable,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    ValuesView,
)
from functools import reduce
from types import TracebackType
from typing import IO, Any, Awaitable

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
        return JsProxy(_instantiate_token)


class ConversionError(Exception):
    """An error thrown when conversion between JavaScript and Python fails."""


# We need this to look up the flags
_core_dict: dict[str, Any] = {}


def _binor_reduce(l: Iterable[int]) -> int:
    return reduce(lambda x, y: x | y, l)


def _process_flag_expression(e: str) -> int:
    return _binor_reduce(_core_dict[x.strip()] for x in e.split("|"))


class _JsProxyMetaClass(type):
    def __instancecheck__(cls, instance):
        """Override for isinstance(instance, cls)."""
        # TODO: add support for user-generated subclasses with custom instance
        # checks
        # e.g., could check for a fetch response with x.constructor.name == "Response"
        # or Object.prototype.toString.call(x) == "[object Response]".
        return cls.__subclasscheck__(type(instance))

    def __subclasscheck__(cls, subclass):
        # TODO: This works for now but maybe there is a better or cleaner way to
        # do this.
        if type.__subclasscheck__(cls, subclass):
            return True
        if not hasattr(subclass, "_js_type_flags"):
            return False
        # For the "synthetic" subtypes defined in this file, we define
        # _js_type_flags as a string. To convert it to the correct value, we
        # exec it in the _core_dict context.
        cls_flags = cls._js_type_flags  # type:ignore[attr-defined]
        if isinstance(cls_flags, int):
            cls_flags = [cls_flags]
        else:
            cls_flags = [_process_flag_expression(f) for f in cls_flags]

        subclass_flags = subclass._js_type_flags
        if not isinstance(subclass_flags, int):
            subclass_flags = _binor_reduce(_core_dict[f] for f in subclass_flags)

        return any(cls_flag & subclass_flags == cls_flag for cls_flag in cls_flags)


# We want to raise an error if someone tries to instantiate JsProxy directly
# since it doesn't mean anything. But we have a few reasons to do so internally.
# So we raise an error unless this private token is passed as an argument.
_instantiate_token = object()


class JsProxy(metaclass=_JsProxyMetaClass):
    """A proxy to make a JavaScript object behave like a Python object

    For more information see the :ref:`type-translations` documentation. In
    particular, see
    :ref:`the list of __dunder__ methods <type-translations-jsproxy>`
    that are (conditionally) implemented on :any:`JsProxy`.
    """

    _js_type_flags: Any = 0

    def __new__(cls, arg=None, *args, **kwargs):
        if arg is _instantiate_token:
            return super().__new__(cls)
        raise TypeError(f"{cls.__name__} cannot be instantiated.")

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
        raise NotImplementedError

    def object_keys(self) -> "JsProxy":
        "The JavaScript API ``Object.keys(object)``"
        raise NotImplementedError

    def object_values(self) -> "JsProxy":
        "The JavaScript API ``Object.values(object)``"
        raise NotImplementedError

    def as_object_map(self) -> "JsMutableMap":
        """Returns a new JsProxy that treats the object as a map.

        The methods ``__getitem__``, ``__setitem__``, ``__contains__``,
        ``__len__``, etc will perform lookups via ``object[key]`` or similar.

        Note that ``len(x.as_object_map())`` evaluates in O(n) time (it iterates
        over the object and counts how many ownKeys it has). If you need to
        compute the length in O(1) time, use a real ``Map`` instead.
        """
        raise NotImplementedError

    def new(self, *args: Any, **kwargs: Any) -> "JsProxy":
        """Construct a new instance of the JavaScript object"""
        raise NotImplementedError

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
        raise NotImplementedError


class JsDoubleProxy(JsProxy):
    """A double proxy created with :any:`create_proxy`."""

    _js_type_flags = ["IS_DOUBLE_PROXY"]

    def destroy(self) -> None:
        pass

    def unwrap(self) -> Any:
        """Unwrap a double proxy created with :any:`create_proxy` into the
        wrapped Python object.
        """
        raise NotImplementedError


class JsPromise(JsProxy):
    """A JsProxy of a promise (or some other awaitable JavaScript object).

    A JavaScript object is considered to be a Promise if it has a "then" method.
    """

    _js_type_flags = ["IS_AWAITABLE"]

    def then(
        self, onfulfilled: Callable[[Any], Any], onrejected: Callable[[Any], Any]
    ) -> "JsPromise":
        """The ``Promise.then`` API, wrapped to manage the lifetimes of the
        handlers.

        Pyodide will automatically release the references to the handlers
        when the promise resolves.
        """
        raise NotImplementedError

    def catch(self, onrejected: Callable[[Any], Any], /) -> "JsPromise":
        """The ``Promise.catch`` API, wrapped to manage the lifetimes of the
        handler.

        Pyodide will automatically release the references to the handler
        when the promise resolves.
        """
        raise NotImplementedError

    def finally_(self, onfinally: Callable[[Any], Any], /) -> "JsPromise":
        """The ``Promise.finally`` API, wrapped to manage the lifetimes of
        the handler.

        Pyodide will automatically release the references to the handler
        when the promise resolves. Note the trailing underscore in the name;
        this is needed because ``finally`` is a reserved keyword in Python.
        """
        raise NotImplementedError


class JsBuffer(JsProxy):
    """A JsProxy of an array buffer or array buffer view"""

    _js_type_flags = ["IS_BUFFER"]
    # There are no types for buffers:
    # https://github.com/python/typing/issues/593
    # https://bugs.python.org/issue27501
    # This is just for docs so lets just make something up?

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign(self, rhs: Any, /) -> None:
        """Assign from a Python buffer into the JavaScript buffer."""

    # Argument should be a buffer.
    # See https://github.com/python/typing/issues/593
    def assign_to(self, to: Any, /) -> None:
        """Assign to a Python buffer from the JavaScript buffer."""

    def to_memoryview(self) -> memoryview:
        """Convert a buffer to a memoryview.

        Copies the data once. This currently has the same effect as :any:`to_py`.
        """
        raise NotImplementedError

    def to_bytes(self) -> bytes:
        """Convert a buffer to a bytes object.

        Copies the data once.
        """
        raise NotImplementedError

    def to_file(self, file: IO[bytes] | IO[str], /) -> None:
        """Writes a buffer to a file.

        Will write the entire contents of the buffer to the current position of
        the file.

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

    def from_file(self, file: IO[bytes] | IO[str], /) -> None:
        """Reads from a file into a buffer.

        Will try to read a chunk of data the same size as the buffer from
        the current position of the file.

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

    def _into_file(self, file: IO[bytes] | IO[str], /) -> None:
        """Will write the entire contents of a buffer into a file using
        ``canOwn : true`` without any copy. After this, the buffer cannot be
        used again.

        If ``file`` is not empty, its contents will be overwritten!

        Only ``MEMFS`` cares about the ``canOwn`` flag, other file systems will
        just ignore it.


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
        """
        raise NotImplementedError


class JsArray(JsProxy):
    """A JsProxy of an array, node list, or typed array"""

    _js_type_flags = ["IS_ARRAY", "IS_NODE_LIST", "IS_TYPEDARRAY"]

    def __getitem__(self, idx: int | slice) -> Any:
        return None

    def __setitem__(self, idx: int | slice, value: Any) -> None:
        pass

    def __delitem__(self, idx: int | slice) -> None:
        pass

    def __len__(self) -> int:
        return 0

    def extend(self, other: Iterable[Any]) -> None:
        """Extend array by appending elements from the iterable."""

    def __reversed__(self) -> Iterator[Any]:
        """Return a reverse iterator over the Array."""
        raise NotImplementedError

    def pop(self, /, index: int = -1) -> Any:
        """Remove and return item at index (default last).

        Raises IndexError if list is empty or index is out of range.
        """
        raise NotImplementedError

    def push(self, /, object: Any) -> None:
        pass

    def append(self, /, object: Any) -> None:
        """Append object to the end of the list."""

    def index(self, /, value: Any, start: int = 0, stop: int = sys.maxsize) -> int:
        """Return first index of value.

        Raises ValueError if the value is not present.
        """
        raise NotImplementedError

    def count(self, /, x: Any) -> int:
        """Return the number of times x appears in the list."""
        raise NotImplementedError

    def reverse(self) -> None:
        """Reverse the array in place.

        Present only if the wrapped Javascript object is an array.
        """


class JsTypedArray(JsBuffer, JsArray):
    _js_type_flags = ["IS_TYPEDARRAY"]
    BYTES_PER_ELEMENT: int

    def subarray(
        self, start: int | None = None, stop: int | None = None
    ) -> "JsTypedArray":
        raise NotImplementedError

    buffer: JsBuffer


@Mapping.register
class JsMap(JsProxy):
    """A JavaScript Map

    To be considered a map, a JavaScript object must have a ``.get`` method, it
    must have a ``.size`` or a ``.length`` property which is a number
    (idiomatically it should be called ``.size``) and it must be iterable.
    """

    _js_type_flags = ["HAS_GET | HAS_LENGTH | IS_ITERABLE", "IS_OBJECT_MAP"]

    def __getitem__(self, idx: Any) -> Any:
        return None

    def __len__(self) -> int:
        return 0

    def __iter__(self) -> Any:
        raise NotImplementedError

    def __contains__(self, idx: Any) -> bool:
        raise NotImplementedError

    def keys(self) -> KeysView[Any]:
        """Return a KeysView for the map.

        Present if the wrapped JavaScript object is a Mapping (i.e., has
        ``get``, ``has``, ``size``, and ``keys`` methods).
        """
        raise NotImplementedError

    def items(self) -> ItemsView[Any, Any]:
        """Return a ItemsView for the map.

        Present if the wrapped JavaScript object is a Mapping (i.e., has
        ``get``, ``has``, ``size``, and ``keys`` methods).
        """
        raise NotImplementedError

    def values(self) -> ValuesView[Any]:
        """Return a ValuesView for the map.

        Present if the wrapped JavaScript object is a Mapping (i.e., has
        ``get``, ``has``, ``size``, and ``keys`` methods).
        """
        raise NotImplementedError

    def get(self, key: Any, default: Any = None) -> Any:
        """If key in self, returns self[key]. Otherwise returns default.

        Present if the wrapped JavaScript object is a Mapping (i.e., has
        ``get``, ``has``, ``size``, and ``keys`` methods).
        """
        raise NotImplementedError


@MutableMapping.register
class JsMutableMap(JsMap):
    """A JavaScript mutable map

    To be considered a mutable map, a JavaScript object must have a ``.get``
    method, a ``.has`` method, a ``.size`` or a ``.length`` property which is a
    number (idiomatically it should be called ``.size``) and it must be
    iterable.

    Instances of the JavaScript builtin ``Map`` class are ``JsMutableMap``s.
    Also proxies returned by :any:`JsProxy.as_object_map` are instances of
    `JsMap`.
    """

    _js_type_flags = ["HAS_GET | HAS_SET | HAS_LENGTH | IS_ITERABLE", "IS_OBJECT_MAP"]

    def pop(self, key: Any, default: Any = None) -> Any:
        """If key in self, return self[key] and remove key from self. Otherwise
        returns default.

        Present if the wrapped JavaScript object is a MutableMapping (i.e., has
        ``get``, ``has``, ``size``, ``keys``, ``set``, and ``delete`` methods).
        """
        raise NotImplementedError

    def setdefault(self, key: Any, default: Any = None) -> Any:
        """If key in self, return self[key]. Otherwise
        sets self[key] = default and returns default.

        Present if the wrapped JavaScript object is a MutableMapping (i.e., has
        ``get``, ``has``, ``size``, ``keys``, ``set``, and ``delete`` methods).
        """
        raise NotImplementedError

    def popitem(self) -> tuple[Any, Any]:
        """Remove some arbitrary key, value pair from the map and returns the
        (key, value) tuple.

        Present if the wrapped JavaScript object is a MutableMapping (i.e., has
        ``get``, ``has``, ``size``, ``keys``, ``set``, and ``delete`` methods).
        """
        raise NotImplementedError

    def clear(self) -> None:
        """Empty out the map entirely.

        Present if the wrapped JavaScript object is a MutableMapping (i.e., has
        ``get``, ``has``, ``size``, ``keys``, ``set``, and ``delete`` methods).
        """

    def update(
        self, other: Mapping[Any, Any] | None = None, **kwargs: dict[str, Any]
    ) -> None:
        """Updates self from other and kwargs.

        If ``other`` is present and is a Mapping or has a ``keys`` method, does

        .. code-block:: python

            for k in other:
                self[k] = other[k]

        If ``other`` is present and lacks a ``keys`` method, does

        .. code-block:: python

            for (k, v) in other:
                self[k] = v

        In all cases this is followed by:

        .. code-block:: python

            for (k, v) in kwargs.items():
                self[k] = v


        Present if the wrapped JavaScript object is a MutableMapping (i.e., has
        ``get``, ``has``, ``size``, ``keys``, ``set``, and ``delete`` methods).
        """

    def __setitem__(self, idx: Any, value: Any) -> None:
        pass

    def __delitem__(self, idx: Any) -> None:
        return None


class JsIterator(JsProxy):
    """A JsProxy of a JavaScript iterator.

    An object is a JsIterator if it has a `next` method. We can't tell if it's
    synchronously iterable or asynchronously iterable, so we implement both and
    if you try to use the wrong one it will fail at runtime.
    """

    _js_type_flags = ["IS_ITERATOR"]

    def send(self, value: Any) -> Any:
        """Send a value into the iterator. This is a wrapper around
        ``jsobj.next(value)``.

        We can't tell whether a JavaScript iterator is a synchronous iterator,
        an asynchronous iterator, or just some object with a "next" method, so
        we include both ``send`` and ``asend``. If the object is not a
        synchronous iterator, then ``send`` will raise a TypeError (but only
        after calling ``jsobj.next()``!).
        """

    def asend(self, value: Any) -> Any:
        """Send a value into the asynchronous iterator. This is a wrapper around
        ``jsobj.next(value)``.

        We can't tell whether a JavaScript iterator is a synchronous iterator,
        an asynchronous iterator, or just some object with a "next" method, so
        we include both ``send`` and ``asend``. If the object is not a
        asynchronous iterator, then ``asend`` will raise a TypeError (but only
        after calling ``jsobj.next()``!).
        """

    def __next__(self):
        pass

    def __iter__(self):
        pass

    def __aiter__(self):
        pass

    def __anext__(self):
        pass


class JsIterable(JsProxy):
    """A JavaScript iterable object

    A JavaScript object is iterable if it has a ``Symbol.iterator`` method.
    """

    _js_type_flags = ["IS_ITERABLE"]

    def __iter__(self):
        pass


class JsAsyncIterable(JsProxy):
    """A JavaScript async iterable object

    A JavaScript object is async iterable if it has a ``Symbol.asyncIterator`` method.
    """

    _js_type_flags = ["IS_ASYNC_ITERABLE"]

    def __aiter__(self):
        pass


class JsGenerator(JsIterable):
    """A JavaScript generator

    A JavaScript object is treated as a generator if it's ``Symbol.typeTag`` is
    ``Generator``. Most likely this will be because it is a true generator
    produced by the JavaScript runtime, but it may be a custom object trying
    hard to pretend to be a generator. It should have ``next``, ``return``, and
    ``throw`` methods.
    """

    _js_type_flags = ["IS_GENERATOR"]

    def send(self, value: Any) -> Any:
        """
        Resumes the execution and "sends" a value into the generator function.

        The ``value`` argument becomes the result of the current yield
        expression. The ``send()`` method returns the next value yielded by the
        generator, or raises ``StopIteration`` if the generator exits without
        yielding another value. When ``send()`` is called to start the
        generator, the argument will be ignored. Unlike in Python, we cannot
        detect that the generator hasn't started yet, and no error will be
        thrown if the argument of a not-started generator is not ``None``.
        """
        raise NotImplementedError

    def throw(
        self,
        type: Exception | type,
        value: Exception | str | Any = None,
        traceback: TracebackType | None = None,
    ) -> Any:
        """
        Raises an exception at the point where the generator was paused, and
        returns the next value yielded by the generator function.

        If the generator exits without yielding another value, a StopIteration
        exception is raised. If the generator function does not catch the
        passed-in exception, or raises a different exception, then that
        exception propagates to the caller.

        In typical use, this is called with a single exception instance similar to the
        way the raise keyword is used.

        For backwards compatibility, however, the second signature is supported,
        following a convention from older versions of Python. The type argument should
        be an exception class, and value should be an exception instance. If the value
        is not provided, the type constructor is called to get an instance. If traceback
        is provided, it is set on the exception, otherwise any existing __traceback__
        attribute stored in value may be cleared.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Raises a GeneratorExit at the point where the generator function was
        paused.

        If the generator function then exits gracefully, is already closed, or
        raises GeneratorExit (by not catching the exception), close returns to
        its caller. If the generator yields a value, a RuntimeError is raised.
        If the generator raises any other exception, it is propagated to the
        caller. close() does nothing if the generator has already exited due to
        an exception or normal exit.
        """

    def __next__(self) -> Any:
        raise NotImplementedError

    def __iter__(self) -> Iterator[Any]:
        raise NotImplementedError


class JsFetchResponse(JsProxy):
    bodyUsed: bool
    ok: bool
    redirected: bool
    status: int
    statusText: str
    type: str
    url: str

    def clone(self) -> "JsFetchResponse":
        raise NotImplementedError

    async def arrayBuffer(self) -> JsBuffer:
        raise NotImplementedError

    async def text(self) -> str:
        raise NotImplementedError

    async def json(self) -> JsProxy:
        raise NotImplementedError


class JsAsyncGenerator(JsIterable):
    """A JavaScript async generator

    A JavaScript object is treated as an async generator if it's
    ``Symbol.typeTag`` is ``AsyncGenerator``. Most likely this will be because
    it is a true async generator produced by the JavaScript runtime, but it may
    be a custom object trying hard to pretend to be an async generator. It
    should have ``next``, ``return``, and ``throw`` methods.
    """

    _js_type_flags = ["IS_ASYNC_GENERATOR"]

    def __anext__(self):
        pass

    def __aiter__(self) -> AsyncIterator[Any]:
        raise NotImplementedError

    def asend(self, value: Any) -> Awaitable[Any]:
        """Resumes the execution and "sends" a value into the async generator
        function.

        The ``value`` argument becomes the result of the current yield
        expression. The awaitable returned by the asend() method will return the
        next value yielded by the generator or raises ``StopAsyncIteration`` if
        the asynchronous generator returns. If the generator returned a value,
        this value is discarded (because in Python async generators cannot
        return a value).

        When ``asend()`` is called to start the generator, the argument will be
        ignored. Unlike in Python, we cannot detect that the generator hasn't
        started yet, and no error will be thrown if the argument of a
        not-started generator is not ``None``.
        """
        raise NotImplementedError

    def athrow(
        self,
        type: Exception | type,
        value: Exception | str | None = None,
        traceback: TracebackType | None = None,
    ) -> Awaitable[Any]:
        """Resumes the execution and raises an exception at the point where the
        generator was paused.

        The awaitable returned by the asend() method will return the next value
        yielded by the generator or raises ``StopAsyncIteration`` if the
        asynchronous generator returns. If the generator returned a value, this
        value is discarded (because in Python async generators cannot return a
        value). If the generator function does not catch the passed-in
        exception, or raises a different exception, then that exception
        propagates to the caller.
        """
        raise NotImplementedError

    def aclose(self) -> Awaitable[None]:
        """Raises a GeneratorExit at the point where the generator function was
        paused.

        If the generator function then exits gracefully, is already closed, or
        raises GeneratorExit (by not catching the exception), close returns to
        its caller. If the generator yields a value, a RuntimeError is raised.
        If the generator raises any other exception, it is propagated to the
        caller. close() does nothing if the generator has already exited due to
        an exception or normal exit.
        """
        raise NotImplementedError


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
) -> JsDoubleProxy:
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
