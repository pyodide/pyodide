import contextlib
import socket
import threading

import pytest

from conftest import only_node

# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
pytestmark = [
    pytest.mark.requires_dynamic_linking,
    pytest.mark.skip_refcount_check,
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


# TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
@pytest.fixture(scope="function")
def selenium_nodesock(selenium_standalone_noload):
    selenium = selenium_standalone_noload

    selenium.run_js(
        """
        globalThis.pyodide = await loadPyodide({
            withNodeSocket: true,
        });
        """
    )
    try:
        yield selenium
    finally:
        selenium.run_js("globalThis.pyodide;")


def test_socket_connect(selenium_nodesock):
    """Test that Python socket can connect to a server and exchange data."""
    TEST_MESSAGE = b"Hello from client"
    RESPONSE_MESSAGE = b"Hello from server"

    server_received = []

    def handler(conn, _addr):
        data = conn.recv(1024)
        server_received.append(data)
        conn.sendall(RESPONSE_MESSAGE)

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                s.sendall({TEST_MESSAGE!r})

                response = s.recv(1024)

                s.close()

                response.decode()
            `);
            """
        )

    assert len(server_received) == 1, "Server should have received data"
    assert server_received[0] == TEST_MESSAGE, (
        f"Server received {server_received[0]!r}, expected {TEST_MESSAGE!r}"
    )
    assert result == RESPONSE_MESSAGE.decode(), (
        f"Client received {result!r}, expected {RESPONSE_MESSAGE!r}"
    )


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

    with tcp_server(handler) as (host, port):
        results = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                responses = []
                for msg in {MESSAGES}:
                    s.sendall(msg)
                    response = s.recv(1024)
                    responses.append(response.decode())

                s.close()
                "-".join(responses)
            `);
            """
        )

    assert len(server_received) == len(MESSAGES), "Server should receive all messages"
    assert results == "-".join([msg.decode() for msg in MESSAGES]), (
        f"Expected echo responses, got {results}"
    )


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

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                data = b"X" * {DATA_SIZE}
                s.sendall(data)

                response = s.recv(1024)
                s.close()
                response.decode()
            `);
            """
        )

    assert len(server_received) == 1, "Server should have received data"
    assert len(server_received[0]) == DATA_SIZE, (
        f"Server received {len(server_received[0])} bytes, expected {DATA_SIZE}"
    )
    assert result == f"Received {DATA_SIZE} bytes"


def test_socket_getpeername(selenium_nodesock):
    """Test socket.getpeername() returns correct remote address."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                peer = s.getpeername()
                s.sendall(b"test")
                s.recv(1024)
                s.close()
                peer
            `);
            """
        )

    assert result[1] == port, f"Expected port {port}, got {result[1]}"
    assert isinstance(result[0], str) and len(result[0]) > 0, (
        f"Expected non-empty host string, got: {result[0]}"
    )


def test_socket_getsockname(selenium_nodesock):
    """Test socket.getsockname() returns local address info."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                local = s.getsockname()
                s.sendall(b"test")
                s.recv(1024)
                s.close()
                local
            `);
            """
        )

    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) >= 2, f"Expected at least 2 elements, got {len(result)}"


def test_socket_connection_refused(selenium_nodesock):
    """Test that connecting to a non-listening port raises an error."""
    # Bind to port 0, get the assigned port, then close immediately.
    # This gives us a port that is almost certainly not listening.
    tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp.bind(("127.0.0.1", 0))
    _, port = tmp.getsockname()
    tmp.close()

    result = selenium_nodesock.run_js(
        f"""
        return await pyodide.runPythonAsync(`
            import socket

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("127.0.0.1", {port}))
                result = "no_error"
            except OSError as e:
                result = f"OSError: {{e.errno}}"
            except Exception as e:
                result = f"Other: {{type(e).__name__}}"
            finally:
                s.close()
            result
        `);
        """
    )
    assert "OSError" in result or "Other" in result, (
        f"Expected connection error, got: {result}"
    )


def test_socket_recv_after_close(selenium_nodesock):
    """Test receiving data after server closes connection."""

    def handler(conn, _addr):
        conn.sendall(b"Final message")

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket
                import time

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                time.sleep(0.5)

                data = s.recv(1024)
                s.close()
                data.decode()
            `);
            """
        )

    assert result == "Final message", f"Expected 'Final message', got {result!r}"


def test_socket_fileno(selenium_nodesock):
    """Test that socket.fileno() returns a valid file descriptor."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                fd_before = s.fileno()

                s.connect(("{host}", {port}))
                fd_after = s.fileno()

                s.sendall(b"test")
                s.recv(1024)
                s.close()

                (fd_before, fd_after)
            `);
            """
        )

    assert isinstance(result[0], int) and result[0] > 0, (
        f"Invalid fd before connect: {result[0]}"
    )
    assert isinstance(result[1], int) and result[1] > 0, (
        f"Invalid fd after connect: {result[1]}"
    )
    assert result[0] == result[1], (
        f"fd changed after connect: {result[0]} -> {result[1]}"
    )


def test_socket_send_recv_partial(selenium_nodesock):
    """Test partial recv when buffer is smaller than data."""
    FULL_MESSAGE = b"A" * 1000

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(FULL_MESSAGE)

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                s.sendall(b"start")

                received = b""
                while len(received) < {len(FULL_MESSAGE)}:
                    chunk = s.recv(100)
                    if not chunk:
                        break
                    received += chunk

                s.close()
                len(received)
            `);
            """
        )

    assert result == len(FULL_MESSAGE), (
        f"Expected {len(FULL_MESSAGE)} bytes, got {result}"
    )


def test_socket_create_multiple(selenium_nodesock):
    """Test creating multiple sockets simultaneously."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        _, sport = conn.getsockname()
        conn.sendall(f"Server{sport}:{data.decode()}".encode())

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                s1.connect(("{host1}", {port1}))
                s2.connect(("{host2}", {port2}))

                s1.sendall(b"Hello1")
                s2.sendall(b"Hello2")

                r1 = s1.recv(1024)
                r2 = s2.recv(1024)

                s1.close()
                s2.close()

                f"{{r1.decode()}}-{{r2.decode()}}"
            `);
            """
        )

    assert result == f"Server{port1}:Hello1-Server{port2}:Hello2"


def test_socket_recv_eof(selenium_nodesock):
    """Test that recv returns b'' after server closes and all data is consumed."""

    def handler(conn, _addr):
        conn.sendall(b"goodbye")
        conn.close()

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket
                import time

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                data = s.recv(1024)

                # Give time for the FIN to arrive
                time.sleep(1.0)

                eof = s.recv(1024)

                s.close()
                (data.decode(), len(eof))
            `);
            """
        )

    assert result[0] == "goodbye", f"Expected 'goodbye', got {result[0]!r}"
    assert result[1] == 0, f"Expected empty bytes (EOF), got {result[1]} bytes"


def test_socket_send_after_remote_close(selenium_nodesock):
    """Test that sending data after the remote side closes raises an error."""

    def handler(conn, _addr):
        conn.close()

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket
                import time

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                # Give time for the FIN to arrive
                time.sleep(0.5)

                error_type = "no_error"
                try:
                    # Send enough data to trigger the error
                    for _ in range(10):
                        s.sendall(b"X" * 4096)
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    error_type = type(e).__name__
                finally:
                    s.close()
                error_type
            `);
            """
        )

    assert result in ("BrokenPipeError", "ConnectionResetError", "OSError"), (
        f"Expected a connection error, got: {result}"
    )


# @pytest.mark.skip(reason="readlines() requires EOF propagation")
def test_socket_makefile(selenium_nodesock):
    """Test socket.makefile() with line-based I/O."""

    def handler(conn, _addr):
        conn.sendall(b"line1\nline2\nline3\n")
        conn.close()

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                f = s.makefile("r")
                lines = f.readlines()
                f.close()
                s.close()
                [l.strip() for l in lines]
            `);
            """
        )

    assert result == ["line1", "line2", "line3"], (
        f"Expected ['line1', 'line2', 'line3'], got {result}"
    )


def test_socket_asyncio_concurrent(selenium_nodesock):
    """Test concurrent socket operations with asyncio.gather."""

    def echo_handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    with (
        tcp_server(echo_handler) as (host1, port1),
        tcp_server(echo_handler) as (host2, port2),
    ):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
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
                    socket_task("{host1}", {port1}, "msg1"),
                    socket_task("{host2}", {port2}, "msg2"),
                )
                f"{{r1}}-{{r2}}"
            `);
            """
        )

    assert result == "msg1-msg2", f"Expected 'msg1-msg2', got {result!r}"


def test_socket_large_recv(selenium_nodesock):
    """Test receiving large data (64KB) from server via recv loop."""
    DATA_SIZE = 64 * 1024  # 64KB

    def handler(conn, _addr):
        conn.recv(1024)  # wait for ready signal
        data = b"Y" * DATA_SIZE
        conn.sendall(data)
        conn.close()

    with tcp_server(handler, timeout=10.0) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                s.sendall(b"ready")

                received = b""
                while len(received) < {DATA_SIZE}:
                    chunk = s.recv(8192)
                    if not chunk:
                        break
                    received += chunk

                s.close()
                (len(received), received == b"Y" * {DATA_SIZE})
            `);
            """
        )

    assert result[0] == DATA_SIZE, (
        f"Expected {DATA_SIZE} bytes, got {result[0]}"
    )
    assert result[1] is True, "Received data content mismatch"


def test_socket_double_close(selenium_nodesock):
    """Test that closing a socket twice does not crash."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
                import socket

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("{host}", {port}))

                s.sendall(b"test")
                s.recv(1024)

                s.close()
                s.close()  # second close should not raise
                "ok"
            `);
            """
        )

    assert result == "ok", f"Expected 'ok', got {result!r}"
