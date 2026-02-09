import socket
import threading
import time

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node


@pytest.fixture(scope="function")
def selenium_nodesock(selenium):
    selenium.run_js("""pyodide.mountNodeSockFS();""")
    yield selenium


@only_node
def test_socket_connect(selenium_nodesock):
    """Test that Python socket can connect to a server and exchange data."""
    PORT = 12345
    TEST_MESSAGE = b"Hello from client"
    RESPONSE_MESSAGE = b"Hello from server"

    server_received = []
    server_error = []

    def run_server():
        """Run a simple echo server in a background thread."""
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)  # 5 second timeout

            conn, _ = server_socket.accept()
            try:
                # Receive data from client
                data = conn.recv(1024)
                server_received.append(data)

                # Send response back
                conn.sendall(RESPONSE_MESSAGE)
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(0.5)

    @run_in_pyodide
    async def socket_client_test(selenium_nodesock, port, message):
        import socket

        # Create socket and connect
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        # Send data
        s.sendall(message)

        # Receive response
        response = s.recv(1024)

        s.close()

        return response

    # Run the client test in Pyodide
    result = socket_client_test(selenium_nodesock, PORT, TEST_MESSAGE)

    # Wait for server thread to finish
    server_thread.join(timeout=5.0)

    # Verify no server errors
    assert not server_error, (
        f"Server error: {server_error[0] if server_error else 'unknown'}"
    )

    # Verify data was received by server
    assert len(server_received) == 1, "Server should have received data"
    assert server_received[0] == TEST_MESSAGE, (
        f"Server received {server_received[0]!r}, expected {TEST_MESSAGE!r}"
    )

    # Verify client received response
    assert result == RESPONSE_MESSAGE, (
        f"Client received {result!r}, expected {RESPONSE_MESSAGE!r}"
    )


@only_node
def test_socket_multiple_send_recv(selenium_nodesock):
    """Test multiple send/recv operations on the same connection."""
    PORT = 12346
    MESSAGES = [b"First message", b"Second message", b"Third message"]

    server_received = []
    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                # Echo back each message
                for _ in range(len(MESSAGES)):
                    data = conn.recv(1024)
                    if data:
                        server_received.append(data)
                        conn.sendall(data)  # Echo back
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def multiple_send_recv_test(selenium, port, messages):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        responses = []
        for msg in messages:
            s.sendall(msg)
            response = s.recv(1024)
            responses.append(response)

        s.close()
        return responses

    results = multiple_send_recv_test(selenium_nodesock, PORT, MESSAGES)
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    assert len(server_received) == len(MESSAGES), "Server should receive all messages"
    assert results == MESSAGES, f"Expected echo responses {MESSAGES}, got {results}"


@only_node
def test_socket_large_data_transfer(selenium_nodesock):
    """Test transferring larger amounts of data."""
    PORT = 12347
    DATA_SIZE = 64 * 1024  # 64KB

    server_received = []
    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(10.0)

            conn, _ = server_socket.accept()
            try:
                # Receive all data
                received = b""
                while len(received) < DATA_SIZE:
                    chunk = conn.recv(8192)
                    if not chunk:
                        break
                    received += chunk
                server_received.append(received)

                # Send acknowledgment with size
                conn.sendall(f"Received {len(received)} bytes".encode())
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def large_data_test(selenium_nodesock, port, data_size):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        # Send large data
        data = b"X" * data_size
        s.sendall(data)

        # Receive acknowledgment
        response = s.recv(1024)
        s.close()
        return response

    result = large_data_test(selenium_nodesock, PORT, DATA_SIZE)
    server_thread.join(timeout=10.0)

    assert not server_error, f"Server error: {server_error}"
    assert len(server_received) == 1, "Server should have received data"
    assert len(server_received[0]) == DATA_SIZE, (
        f"Server received {len(server_received[0])} bytes, expected {DATA_SIZE}"
    )
    assert result == f"Received {DATA_SIZE} bytes".encode()


@only_node
def test_socket_getpeername(selenium_nodesock):
    """Test socket.getpeername() returns correct remote address."""
    PORT = 12348

    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                conn.recv(1024)
                conn.sendall(b"OK")
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def getpeername_test(selenium_nodesock, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        peer = s.getpeername()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return peer

    result = getpeername_test(selenium_nodesock, PORT)
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    # getpeername should return (host, port)
    assert result[1] == PORT, f"Expected port {PORT}, got {result[1]}"
    # Host can be various addresses depending on environment (localhost, 127.0.0.1, ::1, or other local IPs)
    assert isinstance(result[0], str) and len(result[0]) > 0, (
        f"Expected non-empty host string, got: {result[0]}"
    )


@only_node
def test_socket_getsockname(selenium_nodesock):
    """Test socket.getsockname() returns local address info."""
    PORT = 12349

    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                conn.recv(1024)
                conn.sendall(b"OK")
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def getsockname_test(selenium_nodesock, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        local = s.getsockname()
        s.sendall(b"test")
        s.recv(1024)
        s.close()
        return local

    result = getsockname_test(selenium_nodesock, PORT)
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    # getsockname should return (host, port) tuple
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) >= 2, f"Expected at least 2 elements, got {len(result)}"


@only_node
def test_socket_connection_refused(selenium_nodesock):
    """Test that connecting to a non-listening port raises an error."""

    @run_in_pyodide
    async def connection_refused_test(selenium_nodesock):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Port 59999 should not have anything listening
            s.connect(("localhost", 59999))
            return "no_error"
        except OSError as e:
            return f"OSError: {e.errno}"
        except Exception as e:
            return f"Other: {type(e).__name__}"
        finally:
            s.close()

    result = connection_refused_test(selenium_nodesock)
    # Should get an OSError (connection refused)
    assert "OSError" in result or "Other" in result, (
        f"Expected connection error, got: {result}"
    )


@only_node
def test_socket_recv_after_close(selenium_nodesock):
    """Test receiving data after server closes connection."""
    PORT = 12350

    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                # Send data then close immediately
                conn.sendall(b"Final message")
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def recv_after_close_test(selenium_nodesock, port):
        import socket
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        # Wait a bit for server to send and close
        time.sleep(0.5)

        # Should still be able to receive buffered data
        data = s.recv(1024)
        s.close()
        return data

    result = recv_after_close_test(selenium_nodesock, PORT)
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    assert result == b"Final message", f"Expected 'Final message', got {result!r}"


@only_node
def test_socket_fileno(selenium_nodesock):
    """Test that socket.fileno() returns a valid file descriptor."""
    PORT = 12351

    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                conn.recv(1024)
                conn.sendall(b"OK")
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def fileno_test(selenium_nodesock, port):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fd_before = s.fileno()

        s.connect(("localhost", port))
        fd_after = s.fileno()

        s.sendall(b"test")
        s.recv(1024)
        s.close()

        return (fd_before, fd_after)

    result = fileno_test(selenium_nodesock, PORT)
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    # File descriptor should be a positive integer
    assert isinstance(result[0], int) and result[0] > 0, (
        f"Invalid fd before connect: {result[0]}"
    )
    assert isinstance(result[1], int) and result[1] > 0, (
        f"Invalid fd after connect: {result[1]}"
    )
    # fd should be the same before and after connect
    assert result[0] == result[1], (
        f"fd changed after connect: {result[0]} -> {result[1]}"
    )


@only_node
def test_socket_send_recv_partial(selenium_nodesock):
    """Test partial recv when buffer is smaller than data."""
    PORT = 12352
    FULL_MESSAGE = b"A" * 1000

    server_error = []

    def run_server():
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", PORT))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                conn.recv(1024)
                conn.sendall(FULL_MESSAGE)
            finally:
                conn.close()
        except Exception as e:
            server_error.append(str(e))
        finally:
            if server_socket:
                server_socket.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def partial_recv_test(selenium_nodesock, port, expected_total):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        s.sendall(b"start")

        # Receive in small chunks
        received = b""
        while len(received) < expected_total:
            chunk = s.recv(100)  # Small buffer
            if not chunk:
                break
            received += chunk

        s.close()
        return len(received)

    result = partial_recv_test(selenium_nodesock, PORT, len(FULL_MESSAGE))
    server_thread.join(timeout=5.0)

    assert not server_error, f"Server error: {server_error}"
    assert result == len(FULL_MESSAGE), (
        f"Expected {len(FULL_MESSAGE)} bytes, got {result}"
    )


@only_node
def test_socket_create_multiple(selenium_nodesock):
    """Test creating multiple sockets simultaneously."""
    PORT1 = 12353
    PORT2 = 12354

    server_error = []

    def run_server(port):
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", port))
            server_socket.listen(1)
            server_socket.settimeout(5.0)

            conn, _ = server_socket.accept()
            try:
                data = conn.recv(1024)
                conn.sendall(f"Server{port}:{data.decode()}".encode())
            finally:
                conn.close()
        except Exception as e:
            server_error.append(f"Port {port}: {e}")
        finally:
            if server_socket:
                server_socket.close()

    thread1 = threading.Thread(target=run_server, args=(PORT1,), daemon=True)
    thread2 = threading.Thread(target=run_server, args=(PORT2,), daemon=True)
    thread1.start()
    thread2.start()
    time.sleep(0.5)

    @run_in_pyodide
    async def multiple_sockets_test(selenium_nodesock, port1, port2):
        import socket

        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s1.connect(("localhost", port1))
        s2.connect(("localhost", port2))

        s1.sendall(b"Hello1")
        s2.sendall(b"Hello2")

        r1 = s1.recv(1024)
        r2 = s2.recv(1024)

        s1.close()
        s2.close()

        return (r1, r2)

    result = multiple_sockets_test(selenium_nodesock, PORT1, PORT2)
    thread1.join(timeout=5.0)
    thread2.join(timeout=5.0)

    assert not server_error, f"Server errors: {server_error}"
    assert result[0] == f"Server{PORT1}:Hello1".encode()
    assert result[1] == f"Server{PORT2}:Hello2".encode()
