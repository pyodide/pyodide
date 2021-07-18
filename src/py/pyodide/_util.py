from io import StringIO

try:
    from js import XMLHttpRequest
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
