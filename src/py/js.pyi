from collections.abc import Callable, Iterable
from typing import Any, Literal, overload

from _pyodide._core_docs import _JsProxyMetaClass
from pyodide.ffi import (
    JsArray,
    JsDomElement,
    JsException,
    JsFetchResponse,
    JsProxy,
    JsTypedArray,
)
from pyodide.webloop import PyodideFuture

def eval(code: str) -> Any: ...

# in browser the cancellation token is an int, in node it's a special opaque
# object.
_CancellationToken = int | JsProxy

def setTimeout(cb: Callable[[], Any], timeout: int | float) -> _CancellationToken: ...
def clearTimeout(id: _CancellationToken) -> None: ...
def setInterval(cb: Callable[[], Any], interval: int | float) -> _CancellationToken: ...
def clearInterval(id: _CancellationToken) -> None: ...
def fetch(
    url: str, options: JsProxy | None = None
) -> PyodideFuture[JsFetchResponse]: ...

self: Any = ...
window: Any = ...

# Shenanigans to convince skeptical type system to behave correctly:
#
# These classes we are declaring are actually JavaScript objects, so the class
# objects themselves need to be instances of JsProxy. So their type needs to
# subclass JsProxy. We do this with a custom metaclass.

class _JsMeta(_JsProxyMetaClass, JsProxy):
    pass

class _JsObject(metaclass=_JsMeta):
    pass

class XMLHttpRequest(_JsObject):
    response: str

    @staticmethod
    def new() -> XMLHttpRequest: ...
    def open(self, method: str, url: str, sync: bool) -> None: ...
    def send(self, body: JsProxy | None = None) -> None: ...

class Object(_JsObject):
    @staticmethod
    def fromEntries(it: Iterable[JsArray[Any]]) -> JsProxy: ...

class Array(_JsObject):
    @staticmethod
    def new() -> JsArray[Any]: ...

class ImageData(_JsObject):
    @staticmethod
    def new(width: int, height: int, settings: JsProxy | None = None) -> ImageData: ...

    width: int
    height: int

class _TypedArray(_JsObject):
    @staticmethod
    def new(
        a: int | Iterable[int | float] | JsProxy | None,
        byteOffset: int = 0,
        length: int = 0,
    ) -> JsTypedArray: ...

class Uint8Array(_TypedArray):
    BYTES_PER_ELEMENT = 1

class Float64Array(_TypedArray):
    BYTES_PER_ELEMENT = 8

class JSON(_JsObject):
    @staticmethod
    def stringify(a: JsProxy) -> str: ...
    @staticmethod
    def parse(a: str) -> JsProxy: ...

class document(_JsObject):
    body: JsDomElement
    children: list[JsDomElement]
    @overload
    @staticmethod
    def createElement(tagName: Literal["canvas"]) -> JsCanvasElement: ...
    @overload
    @staticmethod
    def createElement(tagName: str) -> JsDomElement: ...
    @staticmethod
    def appendChild(child: JsDomElement) -> None: ...

class JsCanvasElement(JsDomElement):
    width: int | float
    height: int | float
    def getContext(
        self,
        ctxType: str,
        *,
        powerPreference: str = "",
        premultipliedAlpha: bool = False,
        antialias: bool = False,
        alpha: bool = False,
        depth: bool = False,
        stencil: bool = False,
    ) -> Any: ...

class ArrayBuffer(_JsObject):
    @staticmethod
    def isView(x: Any) -> bool: ...

class DOMException(JsException):
    pass

class Map:
    @staticmethod
    def new(a: Iterable[Any]) -> Map: ...
