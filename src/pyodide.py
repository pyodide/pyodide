"""
A library of helper utilities for connecting Python to the browser environment.
"""

from js import XMLHttpRequest

import io


def open_url(url):
    """
    Fetches a given *url* and returns a io.StringIO to access its contents.
    """
    req = XMLHttpRequest.new()
    req.open('GET', url, False)
    req.send(None)
    return io.StringIO(req.response)


__all__ = ['open_url']
