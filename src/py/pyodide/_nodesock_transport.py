"""asyncio Transport backed by NodeSockFS (Node.js native sockets).

This module is Node.js-specific and is imported lazily by
:py:meth:`~pyodide.webloop.WebLoop.create_connection` only when a socket
connection is requested.
"""

import asyncio
from typing import Any


class NodeSocketTransport(asyncio.Transport):
    """asyncio Transport backed by a NodeSockFS socket.

    Uses the JS-level ``_nodeSock.recv`` / ``_nodeSock.send`` helpers so
    that data flows through normal JS Promises rather than JSPI WASM stack
    suspension (which corrupts the Python thread state in an asyncio context).

    Implements the ``BufferedProtocol`` data path: the read loop calls
    ``protocol.get_buffer()`` / ``protocol.buffer_updated()`` to feed incoming
    data without an extra copy into an intermediate ``bytes`` object.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        sock: Any,  # socket.socket — not imported at module level
        protocol: asyncio.BaseProtocol,
        waiter: asyncio.Future[None] | None = None,
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(extra)
        self._loop = loop
        self._sock = sock
        self._sock_fd = sock.fileno()
        self._protocol = protocol
        self._closing = False
        self._closed = False
        self._paused = True  # start paused; resume_reading() will kick off reads
        self._read_task: asyncio.Task[None] | None = None

        self._extra.setdefault("socket", sock)  # type: ignore[attr-defined]
        try:
            self._extra.setdefault("sockname", sock.getsockname())  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self._extra.setdefault("peername", sock.getpeername())  # type: ignore[attr-defined]
        except Exception:
            pass

        # Wire up: connection_made -> resolve waiter.
        # Reading is NOT started automatically.  pymongo (and most protocol
        # implementations) call transport.resume_reading() explicitly after
        # sending a command, so we wait for that instead of eagerly reading
        # from the socket (which would call recvmsgAsync before any request
        # is sent and could race against the Node.js data-event plumbing).
        loop.call_soon(self._protocol.connection_made, self)
        if waiter is not None:
            loop.call_soon(self._resolve_waiter, waiter)

    @staticmethod
    def _resolve_waiter(waiter: asyncio.Future[None]) -> None:
        if not waiter.done():
            waiter.set_result(None)

    # ------------------------------------------------------------------
    # BaseTransport
    # ------------------------------------------------------------------

    def is_closing(self) -> bool:
        return self._closing

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._stop_reading()
        self._loop.call_soon(self._call_connection_lost, None)

    def abort(self) -> None:
        if self._closed:
            return
        if not self._closing:
            self._closing = True
        self._stop_reading()
        try:
            self._sock.close()
        except Exception:
            pass
        self._loop.call_soon(self._call_connection_lost, None)

    def _call_connection_lost(self, exc: BaseException | None) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._protocol.connection_lost(exc)  # type: ignore[arg-type]
        except Exception:
            pass
        try:
            self._sock.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # ReadTransport
    # ------------------------------------------------------------------

    def is_reading(self) -> bool:
        return not self._paused and not self._closing

    def pause_reading(self) -> None:
        self._paused = True

    def resume_reading(self) -> None:
        if self._closing or self._closed:
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
            while not self._paused and not self._closing:
                if isinstance(self._protocol, asyncio.BufferedProtocol):
                    buf = self._protocol.get_buffer(-1)
                    if not len(buf):
                        break

                    data = await _nodeSock.recv(self._sock_fd, len(buf))
                    nbytes = len(data)
                    if nbytes == 0:
                        self._protocol.buffer_updated(0)
                        if not self._closing:
                            self._closing = True
                            self._loop.call_soon(self._call_connection_lost, None)
                        break

                    buf[:nbytes] = bytes(data)
                    self._protocol.buffer_updated(nbytes)
                else:
                    data = await _nodeSock.recv(self._sock_fd, 65536)
                    nbytes = len(data)
                    if nbytes == 0:
                        self._protocol.eof_received()  # type: ignore[attr-defined]
                        if not self._closing:
                            self._closing = True
                            self._loop.call_soon(self._call_connection_lost, None)
                        break

                    self._protocol.data_received(bytes(data))  # type: ignore[attr-defined]

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._force_close(exc)

    def _force_close(self, exc: BaseException | None) -> None:
        if self._closed:
            return
        if not self._closing:
            self._closing = True
        self._stop_reading()
        self._loop.call_soon(self._call_connection_lost, exc)

    # ------------------------------------------------------------------
    # WriteTransport
    # ------------------------------------------------------------------

    def set_write_buffer_limits(
        self, high: int | None = None, low: int | None = None
    ) -> None:
        pass

    def get_write_buffer_size(self) -> int:
        return 0

    def write(self, data: bytes | bytearray | memoryview) -> None:
        if self._closing or self._closed:
            return
        if not data:
            return
        try:
            from pyodide_js._api import _nodeSock

            _nodeSock.send(self._sock_fd, data)
        except Exception as exc:
            self._force_close(exc)

    def write_eof(self) -> None:
        pass

    def can_write_eof(self) -> bool:
        return False
