from io import StringIO
from ._core import JsProxy, to_js
from typing import Any
import json

try:
    from js import XMLHttpRequest
except ImportError:
    pass

from ._core import IN_BROWSER

if IN_BROWSER:
    from js import fetch as _jsfetch, Object


def open_url(url: str) -> StringIO:
    """Fetches a given URL synchronously.

    The download of binary files is not supported. To download binary
     files use :func:`pyodide.utils.fetch` which is asynchronous.

    Parameters
    ----------
    url : str
       URL to fetch

    Returns
    -------
    io.StringIO
        the contents of the URL.
    """

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send(None)
    return StringIO(req.response)


class FetchResponse:
    """A wrapper for a Javascript fetch response.

    See also the Javascript fetch
    `Response <https://developer.mozilla.org/en-US/docs/Web/API/Response>`_ api
    docs.

    Parameters
    ----------
    url
        URL to fetch
    js_response
        A JsProxy of the fetch response
    """

    def __init__(self, url: str, js_response: JsProxy):
        self._url = url
        self.js_response = js_response

    @property
    def body_used(self) -> bool:
        """Has the response been used yet?

        (If so, attempting to retreive the body again will raise an OSError.)
        """
        return self.js_response.bodyUsed

    @property
    def ok(self) -> bool:
        """Was the request successful?"""
        return self.js_response.ok

    @property
    def redirected(self) -> bool:
        """Was the request redirected?"""
        return self.js_response.redirected

    @property
    def status(self) -> str:
        """Response status code"""
        return self.js_response.status

    @property
    def status_text(self) -> str:
        """Response status text"""
        return self.js_response.statusText

    @property
    def type(self) -> str:
        """The `type <https://developer.mozilla.org/en-US/docs/Web/API/Response/type>`_ of the response."""
        return self.js_response.type

    @property
    def url(self) -> str:
        """The `url <https://developer.mozilla.org/en-US/docs/Web/API/Response/url>`_ of the response.

        It may be different than the url passed to fetch.
        """
        return self.js_response.url

    def _raise_if_failed(self):
        if self.js_response.status >= 400:
            raise OSError(
                f"Request for {self._url} failed with status {self.status}: {self.status_text}"
            )
        if self.js_response.bodyUsed:
            raise OSError("Response body is already used")

    def clone(self) -> "FetchResponse":
        """Return an identical copy of the FetchResponse.

        This method exists to allow multiple uses of response objects. See
        `Response.clone <https://developer.mozilla.org/en-US/docs/Web/API/Response/clone>`_
        """
        if self.js_response.bodyUsed:
            raise OSError("Response body is already used")
        return FetchResponse(self._url, self.js_response.clone())

    async def buffer(self) -> JsProxy:
        """Return the response body as a Javascript ArrayBuffer"""
        self._raise_if_failed()
        return await self.js_response.arrayBuffer()

    async def string(self) -> str:
        """Return the response body as a string"""
        self._raise_if_failed()
        return await self.js_response.text()

    async def json(self, **kwargs) -> Any:
        """Return the response body as a Javascript JSON object.

        Any keyword arguments are passed to `json.loads
        <https://docs.python.org/3.8/library/json.html#json.loads>`_.
        """
        self._raise_if_failed()
        return json.loads(await self.string(), **kwargs)

    async def memoryview(self) -> memoryview:
        """Return the response body as a memoryview object"""
        self._raise_if_failed()
        return (await self.buffer()).to_memoryview()

    async def bytes(self) -> bytes:
        """Return the response body as a bytes object"""
        self._raise_if_failed()
        return (await self.buffer()).to_bytes()


async def pyfetch(url, **kwargs) -> FetchResponse:
    """Fetch the url and return the response.

    This functions provides a similar API to the JavaScript `fetch function
    <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`_ however it is
    designed to be convenient to use from Python. The
    :class:`pyodide.utils.FetchResponse` has methods with the output types
    already converted to Python objects.

    Parameters
    ----------
    url URL to fetch. **kwargs Any keyword arguments are passed along as
        `optional parameters to the fetch API
        <https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters>`_.
    """
    return FetchResponse(
        url, await _jsfetch(url, to_js(kwargs, dict_converter=Object.fromEntries))
    )
