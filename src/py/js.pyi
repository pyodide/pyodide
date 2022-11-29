from asyncio import Future
from typing import Any, Callable, Iterable

from _pyodide._core_docs import _JsProxyMetaClass
from pyodide.ffi import JsArray, JsBuffer, JsFetchResponse, JsProxy, JsTypedArray
from pyodide.webloop import PyodideFuture

def eval(code: str) -> Any: ...

class XMLHttpRequest:
    @staticmethod
    def new() -> "XMLHttpRequest": ...
    def open(self, method: str, url: str, sync: bool) -> None: ...
    def send(self, body: JsProxy | None = None) -> None: ...

    response: str

# in browser the cancellation token is an int, in node it's a special opaque
# object.
CancellationToken = int | JsProxy

def setTimeout(cb: Callable[[], Any], timeout: int | float) -> CancellationToken: ...
def clearTimeout(id: CancellationToken) -> None: ...
def setInterval(cb: Callable[[], Any], interval: int | float) -> CancellationToken: ...
def clearInterval(id: CancellationToken) -> None: ...
def fetch(
    url: str, options: JsProxy | None = None
) -> PyodideFuture[JsFetchResponse]: ...

self: Any = ...
window: Any = ...

# Shenanigans to convince skeptical type system to behave correctly
class _JsMeta(_JsProxyMetaClass, JsProxy):
    pass

class _Js(metaclass=_JsMeta):
    pass

class Object(_Js):
    @staticmethod
    def fromEntries(it: Iterable[tuple[str, Any]]) -> JsProxy: ...

class Array(_Js):
    @staticmethod
    def new() -> JsArray: ...

class ImageData(_Js):
    @staticmethod
    def new(width: int, height: int, settings: JsProxy | None = None) -> ImageData: ...

    width: int
    height: int

class _TypedArray(_Js):
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

class JSON:
    @staticmethod
    def stringify(a: JsProxy) -> str: ...
    @staticmethod
    def parse(a: str) -> JsProxy: ...

class JsElement(JsProxy):
    tagName: str
    children: list[JsElement]
    def appendChild(self, child: JsElement) -> None: ...

class document:
    body: JsElement
    children: list[JsElement]
    @staticmethod
    def createElement(tagName: str) -> JsElement: ...
    @staticmethod
    def appendChild(child: JsElement) -> None: ...
