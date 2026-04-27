import contextlib
import socket
import threading
from pathlib import Path

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


def test_socket_shutdown(selenium_nodesock):
    """Test that shutting down a socket works."""

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

        s.shutdown(socket.SHUT_RDWR)
        s.close()

    with tcp_server(handler) as (host, port):
        run(selenium_nodesock, host, port)


def test_socket_shutdown_non_nodesock(selenium_standalone):
    """
    Calling shutdown on a non-node socket will raise "Function not implemented"
    """

    @run_in_pyodide(packages=["pytest"])
    def run(selenium):
        import socket

        import pytest

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)

        assert hasattr(s, "shutdown"), "shutdown method should exist"

        with pytest.raises(OSError, match="Function not implemented"):
            s.shutdown(socket.SHUT_RDWR)

        s.close()

    run(selenium_standalone)


# ---------------------------------------------------------------------------
# asyncio webloop tests
# ---------------------------------------------------------------------------


def test_asyncio_sock_connect_recv_sendall(selenium_nodesock):
    """Test low-level sock_connect + sock_recv + sock_sendall via asyncio."""
    TEST_MESSAGE = b"async hello"
    RESPONSE = b"async reply"

    def handler(conn, _addr):
        _ = conn.recv(1024)
        conn.sendall(RESPONSE)

    @run_in_pyodide
    async def run(selenium, host, port, message):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        await loop.sock_connect(s, (host, port))
        await loop.sock_sendall(s, message)
        data = await loop.sock_recv(s, 1024)
        s.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port, TEST_MESSAGE)
        assert result == RESPONSE.decode()


def test_asyncio_create_connection_echo(selenium_nodesock):
    """Test create_connection with an echo protocol."""

    def handler(conn, _addr):
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        class EchoClient(asyncio.Protocol):
            def __init__(self):
                self.received = bytearray()
                self.done = asyncio.get_event_loop().create_future()

            def data_received(self, data):
                self.received.extend(data)

            def connection_lost(self, exc):
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        transport, proto = await loop.create_connection(EchoClient, host, port)

        transport.write(b"First")
        transport.write(b"Second")
        transport.write(b"Third")

        await asyncio.sleep(1)
        transport.close()
        await asyncio.wait_for(proto.done, timeout=5.0)
        return proto.received.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result


def test_asyncio_create_connection_server_closes(selenium_nodesock):
    """Server sends data then closes; transport should detect EOF."""

    def handler(conn, _addr):
        conn.sendall(b"goodbye")
        conn.close()

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        class Receiver(asyncio.Protocol):
            def __init__(self):
                self.received = bytearray()
                self.lost_exc = "not_called"
                self.done = asyncio.get_event_loop().create_future()

            def data_received(self, data):
                self.received.extend(data)

            def connection_lost(self, exc):
                self.lost_exc = repr(exc)
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        _, proto = await loop.create_connection(Receiver, host, port)

        await asyncio.wait_for(proto.done, timeout=5.0)
        return (proto.received.decode(), proto.lost_exc)

    with tcp_server(handler) as (host, port):
        data, exc = run(selenium_nodesock, host, port)
        assert data == "goodbye"
        assert exc == "None"


def test_asyncio_open_connection(selenium_nodesock):
    """Test asyncio.open_connection (StreamReader/Writer API)."""
    RESPONSE = b"stream reply"

    def handler(conn, _addr):
        _ = conn.recv(1024)
        conn.sendall(RESPONSE)
        conn.close()

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        reader, writer = await asyncio.open_connection(host, port)

        writer.write(b"hello")
        await writer.drain()

        data = await reader.read(1024)
        writer.close()
        return data.decode()

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == RESPONSE.decode()


def test_asyncio_sock_recv_into(selenium_nodesock):
    """Test sock_recv_into fills a buffer."""
    RESPONSE = b"buffer test"

    def handler(conn, _addr):
        conn.sendall(RESPONSE)

    @run_in_pyodide
    async def run(selenium, host, port, expected_len):
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)

        await loop.sock_connect(s, (host, port))

        buf = bytearray(1024)
        n = await loop.sock_recv_into(s, buf)
        s.close()
        return (n, buf[:n].decode())

    with tcp_server(handler) as (host, port):
        n, data = run(selenium_nodesock, host, port, len(RESPONSE))
        assert n == len(RESPONSE)
        assert data == RESPONSE.decode()


def test_asyncio_concurrent_connections(selenium_nodesock):
    """Two concurrent open_connection calls via asyncio.gather."""

    def handler(conn, _addr):
        data = conn.recv(1024)
        conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host1, port1, host2, port2):
        import asyncio

        async def do_echo(host, port, msg):
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(msg)
            await writer.drain()
            data = await reader.read(1024)
            writer.close()
            return data.decode()

        r1, r2 = await asyncio.gather(
            do_echo(host1, port1, b"conn1"),
            do_echo(host2, port2, b"conn2"),
        )
        return (r1, r2)

    with (
        tcp_server(handler) as (host1, port1),
        tcp_server(handler) as (host2, port2),
    ):
        result = run(selenium_nodesock, host1, port1, host2, port2)
        assert result[0] == "conn1"
        assert result[1] == "conn2"


def test_asyncio_client_close_lifecycle(selenium_nodesock):
    """Verify transport.close() triggers connection_lost(None)."""

    def handler(conn, _addr):
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)

    @run_in_pyodide
    async def run(selenium, host, port):
        import asyncio

        events = []

        class Tracker(asyncio.Protocol):
            def __init__(self):
                self.done = asyncio.get_event_loop().create_future()

            def connection_made(self, transport):
                events.append("connection_made")
                self.transport = transport

            def data_received(self, data):
                events.append(f"data:{data.decode()}")

            def connection_lost(self, exc):
                events.append(f"connection_lost:{exc}")
                if not self.done.done():
                    self.done.set_result(None)

        loop = asyncio.get_event_loop()
        transport, proto = await loop.create_connection(Tracker, host, port)

        transport.write(b"ping")
        await asyncio.sleep(0.5)

        assert not transport.is_closing()
        transport.close()
        # Give some time for the close to propagate
        await asyncio.sleep(0.1)
        assert transport.is_closing()

        await asyncio.wait_for(proto.done, timeout=5.0)
        return ",".join(events)

    with tcp_server(handler) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert "connection_made" in result
        assert "connection_lost:None" in result


# ---------------------------------------------------------------------------
# TLS tests
# ---------------------------------------------------------------------------


@pytest.fixture
def self_signed_cert(tmp_path):
    import datetime
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    certfile = tmp_path / "cert.pem"
    keyfile = tmp_path / "key.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    Path(certfile).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    Path(keyfile).write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return certfile, keyfile


@contextlib.contextmanager
def tls_server(handler, certfile, keyfile, *, timeout=5.0):
    """Start a TLS server with a self-signed cert. Yields (host, port)."""
    import ssl as host_ssl

    server_ctx = host_ssl.SSLContext(host_ssl.PROTOCOL_TLS_SERVER)  # type: ignore[attr-defined]
    server_ctx.load_cert_chain(certfile, keyfile)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()
    tls_sock = server_ctx.wrap_socket(server_socket, server_side=True)

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = tls_sock.accept()
            try:
                handler(conn, addr)
            finally:
                conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            tls_sock.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port
    finally:
        thread.join(timeout=timeout)
        assert not errors, f"TLS server error: {errors[0]}"


@pytest.mark.skip_refcount_check
def test_tls_starttls_send_recv(selenium_nodesock, self_signed_cert):
    """Connect plain TCP, upgrade via wrap_socket/startTls, exchange data over TLS."""
    RESPONSE = b"TLS OK"

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(RESPONSE)

    @run_in_pyodide
    def run(selenium, host, port):
        import socket
        import ssl

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # type: ignore[attr-defined]
        ctx.check_hostname = False

        ss = ctx.wrap_socket(s, server_hostname="localhost")
        ss.sendall(b"Hello TLS")
        response = ss.recv(1024)
        ss.close()
        return response.decode()

    with tls_server(handler, *self_signed_cert) as (host, port):
        result = run(selenium_nodesock, host, port)
        assert result == RESPONSE.decode()
