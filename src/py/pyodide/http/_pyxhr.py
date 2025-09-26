"""XMLHttpRequest-based HTTP client for Pyodide.

Provides a requests-like synchronous HTTP API using XMLHttpRequest,
designed specifically for browser environments where traditional HTTP libraries don't work.

Examples
--------
>>> from pyodide.http import pyxhr  # doctest: +RUN_IN_PYODIDE
>>> try:
...     from js import XMLHttpRequest
... except ImportError:
...     import pytest; pytest.skip("XMLHttpRequest not available")
>>> response = pyxhr.get("data:text/plain,Hello World")
>>> response.status_code
200
>>> response.text
'Hello World'
"""

import base64
import json
from typing import Any, NotRequired, TypedDict, Unpack
from urllib.parse import urlencode

from ..ffi import IN_PYODIDE
from ._exceptions import HttpStatusError, XHRError, XHRNetworkError

if IN_PYODIDE:
    try:
        from js import XMLHttpRequest
        from pyodide.ffi import JsException
    except ImportError:
        pass


class XHRRequestParams(TypedDict):
    """Parameters for XMLHttpRequest operations."""

    headers: NotRequired[dict[str, str]]
    params: NotRequired[dict[str, Any]]
    data: NotRequired[str | bytes]
    json: NotRequired[dict[str, Any] | list[Any]]
    auth: NotRequired[tuple[str, str] | list[str]]


class XHRResponse:
    """A wrapper for XMLHttpRequest response that provides a requests-like interface.

    This class wraps the XMLHttpRequest object and provides convenient methods
    to access response data in a manner similar to the requests library.

    Parameters
    ----------
    xhr : Any
        The XMLHttpRequest object to wrap (or any compatible object)
    """

    def __init__(self, xhr: Any):
        self._xhr = xhr
        self._headers_dict: dict[str, str] | None = None

    @property
    def status_code(self) -> int:
        """HTTP status code of the response."""
        return self._xhr.status

    @property
    def content(self) -> bytes:
        """Response content as raw bytes. This is the single source of truth."""
        if hasattr(self._xhr, "response") and self._xhr.response:
            try:
                return bytes(self._xhr.response)
            except (TypeError, ValueError):
                return self._xhr.responseText.encode("utf-8")

        return self._xhr.responseText.encode("utf-8")

    @property
    def text(self) -> str:
        """Response content as text, decoded from the `content` property."""
        return self.content.decode("utf-8")

    @property
    def headers(self) -> dict[str, str]:
        """Response headers as dictionary."""
        if self._headers_dict is None:
            self._headers_dict = self._parse_headers()
        return self._headers_dict

    @property
    def ok(self) -> bool:
        """True if status_code is less than 400."""
        return 200 <= self.status_code < 400

    @property
    def url(self) -> str:
        """Final URL location of response."""
        return self._xhr.responseURL if hasattr(self._xhr, "responseURL") else ""

    def _parse_headers(self) -> dict[str, str]:
        """Parse response headers from XMLHttpRequest."""
        headers: dict[str, str] = {}
        headers_str = self._xhr.getAllResponseHeaders()
        if not headers_str:
            return headers
        for line in headers_str.strip().split("\r\n"):
            if ":" in line:
                key, value = line.split(": ", 1)
                headers[key.strip().lower()] = value.strip()
        return headers

    def json(self, **kwargs: Any) -> Any:
        """Parse response content as JSON.

        Parameters
        ----------
        **kwargs
            Keyword arguments passed to json.loads()

        Returns
        -------
        dict | list | Any
            Parsed JSON data
        """
        return json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        """Raise an exception if the request was unsuccessful."""
        if 400 <= self.status_code < 600:
            raise HttpStatusError(self.status_code, self._xhr.statusText, self.url)


def _xhr_request(
    method: str, url: str, **kwargs: Unpack[XHRRequestParams]
) -> XHRResponse:
    """Make a synchronous HTTP request using XMLHttpRequest.

    This is the core function that wraps XMLHttpRequest to provide
    a requests-like interface for synchronous HTTP operations.

    Parameters
    ----------
    method : str
        HTTP method (GET, POST, PUT, DELETE, etc.)
    url : str
        URL to request
    headers : dict, optional
        HTTP headers to send
    params : dict, optional
        URL parameters to append as query string
    data : str or bytes, optional
        Data to send in the request body
    json : dict, optional
        JSON data to send (automatically sets Content-Type)
    auth : tuple, optional
        Basic authentication (username, password)

    Returns
    -------
    XHRResponse
        Wrapped XMLHttpRequest response

    Raises
    ------
    XHRNetworkError
        For network-related errors
    """
    if not IN_PYODIDE:
        raise RuntimeError("XMLHttpRequest is only available in browser environments")

    req = XMLHttpRequest.new()

    if params := kwargs.get("params"):
        if isinstance(params, dict):
            query_string = urlencode(params)
            # Use '&' if URL already has query parameters (contains '?'), otherwise use '?'
            # Case 1: "/get?p1=hello" + params -> "/get?p1=hello&p2=world"
            # Case 2: "/get" + params -> "/get?p1=hello"
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query_string}"

    req.open(method.upper(), url, False)

    # Note: timeout cannot be set for synchronous requests in browsers
    # The timeout parameter is ignored for sync XHR

    headers = kwargs.get("headers", {})

    if auth := kwargs.get("auth"):
        if len(auth) == 2:
            username, password = auth
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers = headers.copy() if headers else {}
            headers["Authorization"] = f"Basic {credentials}"

    json_data = kwargs.get("json")
    data = kwargs.get("data")

    if json_data is not None:
        data = json.dumps(json_data)
        headers = headers.copy() if headers else {}
        headers["Content-Type"] = "application/json"

    for key, value in headers.items():
        req.setRequestHeader(key, str(value))

    try:
        req.send(data)
    except JsException as e:
        if e.name == "NetworkError":
            raise XHRNetworkError(f"Network error for {method} {url}") from e
        raise XHRError(f"XMLHttpRequest failed: {e}") from e

    return XHRResponse(req)


def get(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a GET request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("GET", url, **kwargs)


def post(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a POST request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("POST", url, **kwargs)


def put(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a PUT request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("PUT", url, **kwargs)


def delete(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a DELETE request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("DELETE", url, **kwargs)


def head(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a HEAD request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("HEAD", url, **kwargs)


def patch(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make a PATCH request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("PATCH", url, **kwargs)


def options(url: str, **kwargs: Unpack[XHRRequestParams]) -> XHRResponse:
    """Make an OPTIONS request.

    Parameters
    ----------
    url : str
        URL to request
    **kwargs
        Additional arguments (headers, params, data, json, auth)

    Returns
    -------
    XHRResponse
        Response object
    """
    return _xhr_request("OPTIONS", url, **kwargs)
