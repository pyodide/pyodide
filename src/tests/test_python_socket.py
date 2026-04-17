import contextlib
import socket
import threading

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node

pytestmark = [
    pytest.mark.requires_dynamic_linking,
    only_node,
]


@contextlib.contextmanager
def tcp_server(handler, *, timeout=5.0):
    """Start a TCP server on an OS-assigned port in a background thread.

    Yields the (host, port) the server is listening on.
    *handler* is called with ``(conn, addr)`` for each accepted connection.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = server_socket.accept()
            try:
                handler(conn, addr)
            finally:
                conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            server_socket.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port
    finally:
        thread.join(timeout=timeout)
        assert not errors, f"Server error: {errors[0]}"


def test_socket_connect(selenium_nodesock):
    """Test that Python socket can connect to a server and exchange data."""
    TEST_MESSAGE = b"Hello from client"
    RESPONSE_MESSAGE = b"Hello from server"

    server_received = []

    def handler(conn, _addr):
        data = conn.recv(1024)
        server_received.append(data)
        conn.sendall(RESPONSE_MESSAGE)

    @run_in_pyodide
    async def run(selenium, host, port, message):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(message)

        response = s.recv(1024)

        s.close()
        return response.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, TEST_MESSAGE)
        assert len(server_received) == 1
        assert server_received[0] == TEST_MESSAGE
        assert result == RESPONSE_MESSAGE.decode()


def test_socket_multiple_send_recv(selenium_nodesock):
    """Test multiple send/recv operations on the same connection."""
    MESSAGES = [b"First message", b"Second message", b"Third message"]

    server_received = []

    def handler(conn, _addr):
        for _ in range(len(MESSAGES)):
            data = conn.recv(1024)
            if data:
                server_received.append(data)
                conn.sendall(data)

    @run_in_pyodide
    def run(selenium, host, port, messages):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        responses = []
        for msg in messages:
            s.sendall(msg)
            response = s.recv(1024)
            responses.append(response.decode())

        s.close()
        return responses

    with tcp_server(handler) as (host, port):
        results = run(selenium_nodesock, host, port, MESSAGES)
        assert len(server_received) == len(MESSAGES)
        assert results == [msg.decode() for msg in MESSAGES]


def test_socket_large_data_transfer(selenium_nodesock):
    """Test transferring larger amounts of data."""
    DATA_SIZE = 64 * 1024  # 64KB

    server_received = []

    def handler(conn, _addr):
        received = b""
        while len(received) < DATA_SIZE:
            chunk = conn.recv(8192)
            if not chunk:
                break
            received += chunk
        server_received.append(received)
        conn.sendall(f"Received {len(received)} bytes".encode())

    @run_in_pyodide
    def run(selenium, host, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        data = b"X" * data_size
        s.sendall(data)

        response = s.recv(1024)
        s.close()
        return response.decode()

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = run(selenium_nodesock, host, port, DATA_SIZE)
        assert len(server_received) == 1
        assert len(server_received[0]) == DATA_SIZE
        assert result == f"Received {DATA_SIZE} bytes"


def test_socket_getpeername(selenium_nodesock):
    """Test socket.getpeername() returns correct remote address."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        peer = s.getpeername()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return peer

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result[1] == port
        assert isinstance(result[0], str) and len(result[0]) > 0, (
            f"Expected non-empty host string, got: {result[0]}"
        )


def test_socket_getsockname(selenium_nodesock):
    """Test socket.getsockname() returns local address info."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        local = s.getsockname()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return local

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert len(result) == 2
        assert isinstance(result[0], str)  # IP
        assert isinstance(result[1], int)  # Port


def test_socket_connection_refused(selenium_nodesock):
    """Test that connecting to a non-listening port raises an error."""
    # Bind to port 0, get the assigned port, then close immediately.
    # This gives us a port that is almost certainly not listening.
    tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp.bind(("127.0.0.1", 0))
    _, port = tmp.getsockname()
    tmp.close()

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, port):
        import socket

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(OSError):
            s.connect(("127.0.0.1", port))

    run(selenium_nodesock, port)


def test_socket_recv_after_close(selenium_nodesock):
    """Test receiving data after server closes connection."""

    def handler(conn, _addr):
        conn.sendall(b"Final message")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        time.sleep(0.5)

        data = s.recv(1024)
        s.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == "Final message"


def test_socket_fileno(selenium_nodesock):
    """Test that socket.fileno() returns a valid file descriptor."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fd_before = s.fileno()

        s.connect((host, port))
        fd_after = s.fileno()

        s.sendall(b"test")
        s.recv(1024)
        s.close()

        return (fd_before, fd_after)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert isinstance(result[0], int) and result[0] > 0
        assert isinstance(result[1], int) and result[1] > 0
        assert result[0] == result[1]


def test_socket_send_recv_partial(selenium_nodesock):
    """Test partial recv when buffer is smaller than data."""
    FULL_MESSAGE = b"A" * 1000

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(FULL_MESSAGE)

    @run_in_pyodide
    def run(selenium, host, port, full_message):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"start")

        received = b""
        while len(received) < len(full_message):
            chunk = s.recv(100)
            if not chunk:
                break
            received += chunk

        s.close()
        return received.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, FULL_MESSAGE)
        assert len(result) == len(FULL_MESSAGE)


def test_socket_create_multiple(selenium_nodesock):
    """Test creating multiple sockets simultaneously."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        _, sport = conn.getsockname()
        conn.sendall(f"Server{sport}:{data.decode()}".encode())

    @run_in_pyodide
    def run(selenium, host1, port1, host2, port2):
        import socket

        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s1.connect((host1, port1))
        s2.connect((host2, port2))

        s1.sendall(b"Hello1")
        s2.sendall(b"Hello2")

        r1 = s1.recv(1024)
        r2 = s2.recv(1024)

        s1.close()
        s2.close()

        return [r1.decode(), r2.decode()]

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result == [f"Server{port1}:Hello1", f"Server{port2}:Hello2"]


def test_socket_recv_eof(selenium_nodesock):
    """Test that recv returns b'' after server closes and all data is consumed."""

    def handler(conn, _addr):
        conn.sendall(b"goodbye")
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        data = s.recv(1024)

        # Give time for the FIN to arrive
        time.sleep(1.0)

        eof = s.recv(1024)

        s.close()
        return (data.decode(), len(eof))

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result[0] == "goodbye"
        assert result[1] == 0


def test_socket_send_after_remote_close(selenium_nodesock):
    """Test that sending data after the remote side closes raises an error."""

    def handler(conn, _addr):
        conn.close()

    @run_in_pyodide(packages=["pytest"])
    def run(selenium, host, port):
        import socket
        import time

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        # Give time for the FIN to arrive
        time.sleep(0.5)

        with pytest.raises(OSError):
            # Send enough data to trigger the error
            for _ in range(10):
                s.sendall(b"X" * 4096)
                time.sleep(0.05)

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_makefile(selenium_nodesock):
    """Test socket.makefile() with line-based I/O."""

    def handler(conn, _addr):
        conn.sendall(b"line1\nline2\nline3\n")
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        f = s.makefile("r")
        lines = f.readlines()
        f.close()
        s.close()
        return [l.strip() for l in lines]

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == ["line1", "line2", "line3"]


def test_socket_asyncio_concurrent(selenium_nodesock):
    """Test concurrent socket operations with asyncio.gather."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host1, port1, host2, port2):
        import asyncio
        import socket

        async def socket_task(host, port, msg):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.sendall(msg.encode())
            data = s.recv(1024)
            s.close()
            return data.decode()

        r1, r2 = await asyncio.gather(
            socket_task(host1, port1, "msg1"), socket_task(host2, port2, "msg2")
        )
        return [r1, r2]

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result == ["msg1", "msg2"]


def test_socket_large_recv(selenium_nodesock):
    """Test receiving large data (64KB) from server via recv loop."""
    DATA_SIZE = 64 * 1024  # 64KB

    def handler(conn, _addr):
        conn.recv(1024)  # wait for ready signal
        data = b"Y" * DATA_SIZE
        conn.sendall(data)
        conn.close()

    @run_in_pyodide
    def run(selenium, host, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"ready")

        received = b""
        while len(received) < data_size:
            chunk = s.recv(8192)
            if not chunk:
                break
            received += chunk

        s.close()
        return (len(received), received == b"Y" * data_size)

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = run(selenium_nodesock, host, port, DATA_SIZE)
        assert result[0] == DATA_SIZE
        assert result[1] is True, "Received data content mismatch"


def test_socket_double_close(selenium_nodesock):
    """Test that closing a socket twice does not crash."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    @run_in_pyodide
    def run(selenium, host, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        s.sendall(b"test")
        s.recv(1024)

        s.close()
        s.close()  # second close should not raise

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)
