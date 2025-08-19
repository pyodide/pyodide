#! /usr/bin/env python3

"""
An implementation of the standard library webbrowser module to open webpages.
Since we're already running a webbrowser, it's really simple...
"""

__all__ = ["open", "open_new", "open_new_tab", "get", "register", "Error"]

from collections.abc import Callable
from typing import Any, cast


class BaseBrowser:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.args = [name]

    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        raise NotImplementedError

    def open_new(self, url: str) -> bool:
        return self.open(url, new=1)

    def open_new_tab(self, url: str) -> bool:
        return self.open(url, new=2)


class GenericBrowser(BaseBrowser):
    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        open(url, new, autoraise)
        return True


class Error(Exception):
    pass


_browsers: dict[str, list[Any]] = {}


def open(url: str, new: int = 0, autoraise: bool = True) -> None:
    from js import window

    window.open(url, "_blank")


def open_new(url: str) -> None:
    return open(url, 1)


def open_new_tab(url: str) -> None:
    return open(url, 2)


def register(
    name: str,
    constructor: Callable[[], BaseBrowser] | None,
    instance: BaseBrowser | None = None,
    *,
    preferred: bool = False,
) -> None:
    if instance is None:
        _browsers[name.lower()] = [constructor, None]
    else:
        _browsers[name.lower()] = [None, instance]


def get(using: str | None = None) -> BaseBrowser:
    if using is None:
        return cast(BaseBrowser, _browsers["default"][1])

    try:
        browser = _browsers[using.lower()]
    except KeyError:
        raise Error(f"could not locate runnable browser type '{using}'") from None

    if browser[1] is None:
        constructor = browser[0]
        if constructor:
            browser[1] = constructor()
        else:
            raise Error(f"no constructor available for browser type '{using}'")
    return cast(BaseBrowser, browser[1])


register("default", None, GenericBrowser())
