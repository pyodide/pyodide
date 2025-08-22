"""
Pyodide HTTP module for web requests.

This module provides utilities for making HTTP requests in the browser environment,
including synchronous XMLHttpRequest support and async fetch API.
"""

from .exceptions import AbortError, BodyUsedError, HttpStatusError
from .pyfetch import FetchResponse, pyfetch

# Keep open_url in __init__ for now, will be moved to pyxhr.py later
from .._package_loader import unpack_buffer
from ..ffi import IN_BROWSER, JsBuffer, JsException, JsFetchResponse, to_js
from io import StringIO

if IN_BROWSER:
    try:
        from js import XMLHttpRequest
    except ImportError:
        pass

__all__ = [
    "open_url",
    "pyfetch",
    "FetchResponse",
    "HttpStatusError",
    "BodyUsedError",
    "AbortError",
]


def open_url(url: str) -> StringIO:
    """Fetches a given URL synchronously.

    The download of binary files is not supported. To download binary files use
    :func:`pyodide.http.pyfetch` which is asynchronous.

    It will not work in Node unless you include an polyfill for :js:class:`XMLHttpRequest`.

    Parameters
    ----------
    url :
       URL to fetch

    Returns
    -------
        The contents of the URL.

    Examples
    --------
    >>> None # doctest: +RUN_IN_PYODIDE
    >>> import pytest; pytest.skip("TODO: Figure out how to skip this only in node")
    >>> url = "https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide-lock.json"
    >>> url_contents = open_url(url)
    >>> import json
    >>> result = json.load(url_contents)
    >>> sorted(list(result["info"].items()))
    [('arch', 'wasm32'), ('platform', 'emscripten_3_1_45'), ('python', '3.11.3'), ('version', '0.24.1')]
    """

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send()
    return StringIO(req.response)