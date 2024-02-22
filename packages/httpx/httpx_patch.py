from contextlib import contextmanager

from httpx._client import AsyncClient, BoundAsyncStream, logger
from httpx._models import Headers, Request, Response
from httpx._transports.default import AsyncResponseStream
from httpx._types import AsyncByteStream
from httpx._utils import Timer

from js import Headers as js_Headers
from js import fetch
from pyodide.ffi import create_proxy


@contextmanager
def acquire_buffer(content):
    if not content:
        yield None
        return
    body_px = create_proxy(content)
    body_buf = body_px.getBuffer("u8")
    try:
        yield body_buf.data
    finally:
        body_px.destroy()
        body_buf.release()

async def js_readable_stream_iter(js_readable_stream):
    reader = js_readable_stream.getReader()
    while True:
        res = await reader.read()
        if res.done:
            return
        yield res.value.to_bytes()


async def _send_single_request(self, request: Request) -> Response:
    """
    Sends a single request, without handling any redirections.
    """
    timer = Timer()
    await timer.async_start()

    if not isinstance(request.stream, AsyncByteStream):
        raise RuntimeError(
            "Attempted to send an sync request with an AsyncClient instance."
        )


    js_headers = js_Headers.new(request.headers.multi_items())
    with acquire_buffer(request.content) as body:
        js_resp = await fetch(str(request.url), method=request.method, headers=js_headers, body=body)


    response = Response(
        status_code=js_resp.status,
        headers=Headers(js_resp.headers),
        stream=AsyncResponseStream(js_readable_stream_iter(js_resp.body)),
    )


    assert isinstance(response.stream, AsyncByteStream)
    response.request = request
    response.stream = BoundAsyncStream(
        response.stream, response=response, timer=timer
    )
    self.cookies.extract_cookies(response)
    response.default_encoding = self._default_encoding

    logger.info(
        'HTTP Request: %s %s "%s %d %s"',
        request.method,
        request.url,
        response.http_version,
        response.status_code,
        response.reason_phrase,
    )

    return response

AsyncClient._send_single_request = _send_single_request
