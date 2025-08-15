#! /usr/bin/env python3

"""
An implementation of the standard library webbrowser module to open webpages.
Since we're already running a webbrowser, it's really simple...
"""

__all__ = ["open", "open_new", "open_new_tab", "get", "register", "Error"]


class Error(Exception):
    pass


_browsers = {}


def open(url: str, new: int = 0, autoraise: bool = True) -> None:
    from js import window

    window.open(url, "_blank")


def open_new(url: str) -> None:
    return open(url, 1)


def open_new_tab(url: str) -> None:
    return open(url, 2)


def register(name, constructor, instance=None, *, preferred=False):
    if instance is None:
        _browsers[name.lower()] = [constructor, None]
    else:
        _browsers[name.lower()] = [None, instance]


def get(using=None):
    if using is None:
        return _browsers["default"][1]

    try:
        browser = _browsers[using.lower()]
    except KeyError:
        raise Error(f"could not locate runnable browser type '{using}'") from None

    if browser[1] is None:
        browser[1] = browser[0]()
    return browser[1]


class GenericBrowser:
    def __init__(self, name=""):
        self.name = name
        self.args = [name]

    def open(self, url, new=0, autoraise=True):
        raise NotImplementedError

    def open_new(self, url):
        return self.open(url, new=1)

    def open_new_tab(self, url):
        return self.open(url, new=2)


class BackgroundBrowser(GenericBrowser):
    def open(self, url, new=0, autoraise=True):
        open(url, new, autoraise)
        return True


register("default", None, BackgroundBrowser())
