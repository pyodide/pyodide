from typing import Any

from ..ffi import JsException


class HttpStatusError(OSError):
    """A subclass of :py:exc:`OSError` raised by :py:meth:`FetchResponse.raise_for_status`
    if the response status is 4XX or 5XX.

    Parameters
    ----------
    status :
       The http status code of the request

    status_text :
       The http status text of the request

    url :
        The url that was requested
    """

    status: int
    status_text: str
    url: str

    def __init__(self, status: int, status_text: str, url: str) -> None:
        self.status = status
        self.status_text = status_text
        self.url = url
        if 400 <= status < 500:
            super().__init__(f"{status} Client Error: {status_text} for url: {url}")
        elif 500 <= status < 600:
            super().__init__(f"{status} Server Error: {status_text} for url: {url}")
        else:
            super().__init__(
                f"{status} Invalid error code not between 400 and 599: {status_text} for url: {url}"
            )

    def __reduce__(self):
        return (
            self.__class__,
            (self.status, self.status_text, self.url),
            self.__dict__,
        )


class BodyUsedError(OSError):
    def __init__(self, *args: Any) -> None:
        super().__init__("Response body is already used")


class AbortError(OSError):
    def __init__(self, reason: JsException) -> None:
        super().__init__(reason.message)


# pyxhr exceptions
class XHRError(OSError):
    """Base exception for XMLHttpRequest errors."""


class XHRNetworkError(XHRError):
    """Network-related XMLHttpRequest error."""
    def __init__(self, message: str = "Network error occurred") -> None:
        super().__init__(message)


class XHRTimeoutError(XHRError):
    """Timeout error for XMLHttpRequest."""
    def __init__(self, timeout: int) -> None:
        super().__init__(f"Request timed out after {timeout}ms")
