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


async def fetch(url, **kwargs):
    """Fetch the url and return the Javascript response.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters).
    """
    return await _jsfetch(url, to_js(kwargs, dict_converter=Object.fromEntries))


async def _raise_if_failed(url, resp):
    if resp.status >= 400:
        raise OSError(
            f"Request for {url} failed with status {resp.status}: {resp.statusText}"
        )


async def fetch_string(url: str, **kwargs) -> str:
    """Fetch a url and return the result as a string.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    The data is copied once.
    """
    resp = fetch(url, **kwargs)
    _raise_if_failed(url, resp)
    return await resp.text()


async def fetch_buffer(url: str, **kwargs) -> JsProxy:
    """Fetch a url and return the result as a ``JsProxy`` to an ``ArrayBuffer``.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    The data is not copied.
    """
    resp = fetch(url, **kwargs)
    _raise_if_failed(url, resp)
    return await resp.arrayBuffer()


def fetch_bytes(url):
    """Fetch a url and return the result as a ``bytes`` object.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    The data is copied once.
    """
    return fetch_buffer(url).tobytes()


def fetch_bytesarray(url):
    """Fetch a url and return the result as a ``bytesarray`` object.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    The data is copied once.
    """
    return fetch_buffer(url).tobytesarray()


def fetch_memoryview(url):
    """Fetch a url and return the result as a ``memoryview`` object.

    Any keyword arguments are passed along as [optional paremeters to the fetch
    API](https://developer.mozilla.org/en-US/docs/Web/API/fetch#parameters). If
    a failure status code (>= 400) is returned by the ``fetch`` request, raises
    an `OsError`.

    The data is copied once.
    """
    return fetch_buffer(url).tomemoryview()
