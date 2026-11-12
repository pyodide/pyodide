"""asyncio Transport backed by NodeSockFS

This module is Node.js-specific and is imported lazily by
:py:meth:`~pyodide.webloop.WebLoop.create_connection` only when a socket
connection is requested.
"""

import asyncio
from typing import Any


class NodeSocketTransport(asyncio.Transport):
    """asyncio Transport backed by a NodeSockFS socket."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        sock: Any,  # socket.socket
        protocol: asyncio.BaseProtocol,
        waiter: asyncio.Future[None] | None = None,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(extra)
        self._loop = loop
        self._sock = sock
        self._sock_fd = sock.fileno()
        self._protocol = protocol
        self._closed = False
        self._paused = True  # start paused; resume_reading() will kick off reads
        self._read_task: asyncio.Task[None] | None = None

        # self._extra is used in `get_extra_info` function.
        # We just swallow exceptions following the _SelectorTransport implementation in CPython
        # https://github.com/python/cpython/blob/fbfc6ccb0abf362a0ecdc02cd0aa2d16c1a4ce44/Lib/asyncio/selector_events.py#L780-L787
        self._extra.setdefault("socket", sock)  # type: ignore[attr-defined]
        try:
            self._extra.setdefault("sockname", sock.getsockname())  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self._extra.setdefault("peername", sock.getpeername())  # type: ignore[attr-defined]
        except Exception:
            pass
        loop.call_soon(self._protocol.connection_made, self)
        if waiter is not None:
            loop.call_soon(self._resolve_waiter, waiter)
        loop.call_soon(self._start_reading)

    @staticmethod
    def _resolve_waiter(waiter: asyncio.Future[None]) -> None:
        if not waiter.done():
            waiter.set_result(None)

    # ------------------------------------------------------------------
    # BaseTransport
    # ------------------------------------------------------------------

    def is_closing(self) -> bool:
        # We don't separate _closing and _closed state
        # because the buffer is managed by Node.js not Python
        # so no drain is handled by Python
        return self._closed

    def close(self) -> None:
        self._force_close(None)

    def abort(self) -> None:
        self._force_close(None)

    def _call_connection_lost(self, exc: Exception | None) -> None:
        if self._closed:
            return

        self._protocol.connection_lost(exc)
        self._sock.close()
        self._closed = True

    def get_protocol(self) -> asyncio.BaseProtocol:
        return self._protocol

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        self._protocol = protocol

    # ------------------------------------------------------------------
    # ReadTransport
    # ------------------------------------------------------------------

    def is_reading(self) -> bool:
        return not self._paused and not self._closed

    def pause_reading(self) -> None:
        self._paused = True

    def resume_reading(self) -> None:
        if self._closed:
            return
        if self._paused:
            self._paused = False
            self._ensure_reading()

    def _start_reading(self) -> None:
        self._paused = False
        self._ensure_reading()

    def _stop_reading(self) -> None:
        self._paused = True
        if self._read_task is not None and not self._read_task.done():
            self._read_task.cancel()
            self._read_task = None

    def _ensure_reading(self) -> None:
        if self._read_task is None or self._read_task.done():
            self._read_task = self._loop.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            from pyodide_js._api import _nodeSock
        except ImportError:
            self._force_close(
                OSError("Node.js socket support not available (_nodeSock)")
            )
            return

        try:
            while self.is_reading():
                if isinstance(self._protocol, asyncio.BufferedProtocol):
                    buf = memoryview(self._protocol.get_buffer(-1))
                    if not buf:
                        break

                    data = await _nodeSock.recv(self._sock_fd, len(buf))
                    nbytes = len(data)
                    if nbytes == 0:
                        self._protocol.buffer_updated(0)
                        self.close()
                        break

                    buf[:nbytes] = bytes(data)
                    self._protocol.buffer_updated(nbytes)
                else:
                    data = await _nodeSock.recv(self._sock_fd, 65536)
                    nbytes = len(data)
                    if nbytes == 0:
                        self._protocol.eof_received()  # type: ignore[attr-defined]
                        self.close()
                        break

                    self._protocol.data_received(bytes(data))  # type: ignore[attr-defined]
        except Exception as exc:
            self._force_close(exc)

    def _force_close(self, exc: Exception | None) -> None:
        if self._closed:
            return
        self._stop_reading()
        self._loop.call_soon(self._call_connection_lost, exc)

    # ------------------------------------------------------------------
    # WriteTransport
    # ------------------------------------------------------------------

    # We just let Node socket handle the buffer limits
    def set_write_buffer_limits(
        self, high: int | None = None, low: int | None = None
    ) -> None:
        pass

    def get_write_buffer_limits(self) -> tuple[int, int]:
        return (0, 0)

    def get_write_buffer_size(self) -> int:
        return 0

    def write(self, data: bytes | bytearray | memoryview) -> None:
        if self._closed:
            return
        if not data:
            return
        try:
            from pyodide_js._api import _nodeSock

            _nodeSock.send(self._sock_fd, data)
        except Exception as exc:
            self._force_close(exc)

    # No half-close support
    def write_eof(self) -> None:
        pass

    def can_write_eof(self) -> bool:
        return False
