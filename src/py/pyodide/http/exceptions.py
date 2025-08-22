"""
HTTP-related exceptions and utilities for Pyodide.
"""

from typing import Any
from ..ffi import JsException


def _construct_abort_reason(reason: Any) -> JsException | None:
    """Construct an abort reason from a given value."""
    if reason is None:
        return None
    return JsException("AbortError", reason)


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