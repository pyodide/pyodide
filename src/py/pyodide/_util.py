from io import StringIO
from ._core import JsProxy, to_js

try:
    from js import XMLHttpRequest, fetch as _jsfetch, Object
except ImportError:
    pass


def open_url(url: str) -> StringIO:
    """
    Fetches a given URL

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


async def _fetch(url, **kwargs):
    resp = await _jsfetch(url, to_js(kwargs, dict_converter=Object.fromEntries))
    if resp.status >= 400:
        raise OSError(
            f"Request for {url} failed with status {resp.status}: {resp.statusText}"
        )
    return resp


async def fetch_string(url: str, **kwargs) -> str:
    """Fetch a url and return the result as a string.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    If getting the result as a bytes, bytesarray, or memoryview is acceptable,
    it is more efficient to use :any:`pyodide.fetch_buffer` and then use
    :any:`JsProxy.tobytes`, :any:`JsProxy.tobytearray`, or
    :any:`JsProxy.tomemoryview`.
    """
    resp = _fetch(url, **kwargs)
    return await resp.text()


async def fetch_buffer(url: str, **kwargs) -> JsProxy:
    """Fetch a url and return the result as a ``JsProxy`` to an ``ArrayBuffer``.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    If you need the result as a string, you can avoid an extra copy by using
    :any:`pyodide.fetch_string` instead.
    """
    resp = _fetch(url, **kwargs)
    return await resp.arrayBuffer()
