import json
from io import StringIO
from typing import IO, Any

from ._package_loader import unpack_buffer
from .ffi import IN_BROWSER, JsBuffer, JsException, JsFetchResponse, to_js

if IN_BROWSER:
    from js import Object

    try:
        from js import fetch as _jsfetch
    except ImportError:
        pass
    try:
        from js import XMLHttpRequest
    except ImportError:
        pass

__all__ = [
    "open_url",
    "pyfetch",
    "FetchResponse",
]


def open_url(url: str) -> StringIO:
    """Fetches a given URL synchronously.

    The download of binary files is not supported. To download binary
    files use :func:`pyodide.http.pyfetch` which is asynchronous.

    Parameters
    ----------
    url :
       URL to fetch

    Returns
    -------
        The contents of the URL.
    """

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send()
    return StringIO(req.response)


class FetchResponse:
    """A wrapper for a Javascript fetch :js:data:`Response`.

    Parameters
    ----------
    url
        URL to fetch
    js_response
        A :any:`JsProxy` of the fetch response
    """

    def __init__(self, url: str, js_response: JsFetchResponse):
        self._url = url
        self.js_response = js_response

    @property
    def body_used(self) -> bool:
        """Has the response been used yet?

        If so, attempting to retrieve the body again will raise an
        :any:`OSError`. Use :py:meth:`~FetchResponse.clone` first to avoid this.
        See :js:attr:`Response.bodyUsed`.
        """
        return self.js_response.bodyUsed

    @property
    def ok(self) -> bool:
        """Was the request successful?

        See :js:attr:`Response.ok`.
        """
        return self.js_response.ok

    @property
    def redirected(self) -> bool:
        """Was the request redirected?

        See :js:attr:`Response.redirected`.
        """
        return self.js_response.redirected

    @property
    def status(self) -> int:
        """Response status code

        See :js:attr:`Response.status`.
        """
        return self.js_response.status

    @property
    def status_text(self) -> str:
        """Response status text

        See :js:attr:`Response.statusText`.
        """
        return self.js_response.statusText

    @property
    def type(self) -> str:
        """The type of the response.

        See :js:attr:`Response.type`.
        """
        return self.js_response.type

    @property
    def url(self) -> str:
        """The url of the response.

        The value may be different than the url passed to fetch.
        See :js:attr:`Response.url`.
        """
        return self.js_response.url

    def _raise_if_failed(self) -> None:
        if self.js_response.status >= 400:
            raise OSError(
                f"Request for {self._url} failed with status {self.status}: {self.status_text}"
            )
        if self.js_response.bodyUsed:
            raise OSError("Response body is already used")

    def clone(self) -> "FetchResponse":
        """Return an identical copy of the :any:`FetchResponse`.

        This method exists to allow multiple uses of :any:`FetchResponse`
        objects. See :js:meth:`Response.clone`.
        """
        if self.js_response.bodyUsed:
            raise OSError("Response body is already used")
        return FetchResponse(self._url, self.js_response.clone())

    async def buffer(self) -> JsBuffer:
        """Return the response body as a Javascript :js:class:`ArrayBuffer`.

        See :js:meth:`Response.arrayBuffer`.
        """
        self._raise_if_failed()
        return await self.js_response.arrayBuffer()

    async def string(self) -> str:
        """Return the response body as a string"""
        self._raise_if_failed()
        return await self.js_response.text()

    async def json(self, **kwargs: Any) -> Any:
        """Treat the response body as a JSON string and use
        :py:func:`json.loads` to parse it into a Python object.

        Any keyword arguments are passed to :py:func:`json.loads`.
        """
        self._raise_if_failed()
        return json.loads(await self.string(), **kwargs)

    async def memoryview(self) -> memoryview:
        """Return the response body as a :any:`memoryview` object"""
        self._raise_if_failed()
        return (await self.buffer()).to_memoryview()

    async def _into_file(self, f: IO[bytes] | IO[str]) -> None:
        """Write the data into an empty file with no copy.

        Warning: should only be used when f is an empty file, otherwise it may
        overwrite the data of f.
        """
        buf = await self.buffer()
        buf._into_file(f)

    async def _create_file(self, path: str) -> None:
        """Uses the data to back a new file without copying it.

        This method avoids copying the data when creating a new file. If you
        want to write the data into an existing file, use

        .. code-block:: python

            buf = await resp.buffer()
            buf.to_file(file)

        Parameters
        ----------
        path : str

            The path to the file to create. The file should not exist but
            it should be in a directory that exists. Otherwise, will raise
            an ``OSError``
        """
        with open(path, "x") as f:
            await self._into_file(f)

    async def bytes(self) -> bytes:
        """Return the response body as a bytes object"""
        self._raise_if_failed()
        return (await self.buffer()).to_bytes()

    async def unpack_archive(
        self, *, extract_dir: str | None = None, format: str | None = None
    ) -> None:
        """Treat the data as an archive and unpack it into target directory.

        Assumes that the file is an archive in a format that :any:`shutil` has
        an unpacker for. The arguments ``extract_dir`` and ``format`` are passed
        directly on to :any:`shutil.unpack_archive`.

        Parameters
        ----------
        extract_dir :
            Directory to extract the archive into. If not provided, the current
            working directory is used.

        format :
            The archive format: one of ``"zip"``, ``"tar"``, ``"gztar"``,
            ``"bztar"``. Or any other format registered with
            :py:func:`shutil.register_unpack_format`. If not provided,
            :py:meth:`unpack_archive` will use the archive file name extension and
            see if an unpacker was registered for that extension. In case none
            is found, a :any:`ValueError` is raised.
        """
        buf = await self.buffer()
        filename = self._url.rsplit("/", -1)[-1]
        unpack_buffer(buf, filename=filename, format=format, extract_dir=extract_dir)


async def pyfetch(url: str, **kwargs: Any) -> FetchResponse:
    r"""Fetch the url and return the response.

    This functions provides a similar API to :js:func:`fetch` however it is
    designed to be convenient to use from Python. The
    :class:`~pyodide.http.FetchResponse` has methods with the output types
    already converted to Python objects.

    Parameters
    ----------
    url :
        URL to fetch.

    \*\*kwargs :
        keyword arguments are passed along as `optional parameters to the fetch API
        <https://developer.mozilla.org/en-US/docs/Web/API/fetch#options>`_.
    """
    try:
        return FetchResponse(
            url, await _jsfetch(url, to_js(kwargs, dict_converter=Object.fromEntries))
        )
    except JsException as e:
        raise OSError(e.message) from None
