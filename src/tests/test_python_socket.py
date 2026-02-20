import contextlib
import socket
import threading

import pytest

from conftest import only_node


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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
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
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
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
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
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
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_getpeername(selenium_nodesock):
    """Test socket.getpeername() returns correct remote address."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_getsockname(selenium_nodesock):
    """Test socket.getsockname() returns local address info."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_connection_refused(selenium_nodesock):
    """Test that connecting to a non-listening port raises an error."""
    # Bind to port 0, get the assigned port, then close immediately.
    # This gives us a port that is almost certainly not listening.
    tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmp.bind(("127.0.0.1", 0))
    _, port = tmp.getsockname()
    tmp.close()

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_recv_after_close(selenium_nodesock):
    """Test receiving data after server closes connection."""

    def handler(conn, _addr):
        conn.sendall(b"Final message")

    with tcp_server(handler) as (host, port):
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_fileno(selenium_nodesock):
    """Test that socket.fileno() returns a valid file descriptor."""

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tcp_server(handler) as (host, port):
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
def test_socket_send_recv_partial(selenium_nodesock):
    """Test partial recv when buffer is smaller than data."""
    FULL_MESSAGE = b"A" * 1000

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(FULL_MESSAGE)

    with tcp_server(handler) as (host, port):
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# skip_refcount_check is needed as selenium_standalone_noload fixture does not initialize global hiwire objects
@pytest.mark.skip_refcount_check
@only_node
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
        # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
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


# ---------------------------------------------------------------------------
# TLS socket tests
# ---------------------------------------------------------------------------

import ipaddress
import os
import ssl


@contextlib.contextmanager
def tls_server(handler, *, timeout=5.0, expect_client_error=False):
    """Start a TLS server with a self-signed cert on an OS-assigned port.

    Yields (host, port, ca_pem) where ca_pem is the PEM certificate string
    that clients should trust.

    If *expect_client_error* is True, server-side TLS errors (e.g. the client
    aborting the handshake) are silently ignored.
    """
    certdir = os.path.join(os.path.dirname(__file__), "test_data")
    certfile = os.path.join(certdir, "tls_cert.pem")
    keyfile = os.path.join(certdir, "tls_key.pem")

    if not os.path.exists(certfile):
        _generate_self_signed_cert(certfile, keyfile)

    with open(certfile) as f:
        ca_pem = f.read()

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(certfile, keyfile)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    server_socket.settimeout(timeout)
    host, port = server_socket.getsockname()

    tls_server_socket = server_ctx.wrap_socket(server_socket, server_side=True)

    errors: list[str] = []
    ready = threading.Event()

    def _serve():
        ready.set()
        try:
            conn, addr = tls_server_socket.accept()
            try:
                handler(conn, addr)
            finally:
                conn.close()
        except Exception as e:
            errors.append(str(e))
        finally:
            tls_server_socket.close()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=timeout)

    try:
        yield host, port, ca_pem
    finally:
        thread.join(timeout=timeout)
        if not expect_client_error:
            assert not errors, f"TLS server error: {errors[0]}"


def _generate_self_signed_cert(certfile, keyfile):
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
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

    os.makedirs(os.path.dirname(certfile), exist_ok=True)
    with open(certfile, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(keyfile, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )


def _tls_run(selenium, host, port, ca_pem, python_body):
    import base64

    ca_b64 = base64.b64encode(ca_pem.encode()).decode()
    return selenium.run_js(
        f"""
        return await pyodide.runPythonAsync(`
import socket, ssl, base64

ca_pem = base64.b64decode("{ca_b64}").decode()

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.load_verify_locations(cadata=ca_pem)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("{host}", {port}))
ss = ctx.wrap_socket(s, server_hostname="localhost")

{python_body}
        `);
        """
    )
    return selenium.run_js(
        f"""
        globalThis._testCaPem = `{ca_pem_escaped}`;
        return await pyodide.runPythonAsync(`
import socket
import ssl
from js import _testCaPem

ca_pem = str(_testCaPem)

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.load_verify_locations(cadata=ca_pem)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("{host}", {port}))
ss = ctx.wrap_socket(s, server_hostname="localhost")

{python_body}
        `);
        """
    )
    return selenium.run_js(
        f"""
        globalThis._testCaPem = `{ca_pem_escaped}`;
        return await pyodide.runPythonAsync(`
import socket
import ssl
from pyodide_js import _testCaPem

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.load_verify_locations(cadata=_testCaPem.to_py())

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("{host}", {port}))
ss = ctx.wrap_socket(s, server_hostname="localhost")

{python_body}
        `);
        """
    )


@pytest.mark.skip_refcount_check
@only_node
def test_tls_wrap_socket(selenium_nodesock):
    TEST_MESSAGE = b"Hello TLS"
    RESPONSE_MESSAGE = b"TLS OK"

    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(RESPONSE_MESSAGE)

    with tls_server(handler) as (host, port, ca_pem):
        result = _tls_run(
            selenium_nodesock,
            host,
            port,
            ca_pem,
            f"""
ss.sendall({TEST_MESSAGE!r})
response = ss.recv(1024)
ss.close()
response.decode()
""",
        )

    assert result == RESPONSE_MESSAGE.decode()


@pytest.mark.skip_refcount_check
@only_node
def test_tls_data_exchange(selenium_nodesock):
    MESSAGES = [b"First", b"Second", b"Third"]

    def handler(conn, _addr):
        for _ in range(len(MESSAGES)):
            data = conn.recv(1024)
            if data:
                conn.sendall(data)

    with tls_server(handler) as (host, port, ca_pem):
        results = _tls_run(
            selenium_nodesock,
            host,
            port,
            ca_pem,
            f"""
responses = []
for msg in {MESSAGES}:
    ss.sendall(msg)
    responses.append(ss.recv(1024).decode())
ss.close()
"-".join(responses)
""",
        )

    assert results == "-".join(m.decode() for m in MESSAGES)


@pytest.mark.skip_refcount_check
@only_node
def test_tls_cipher_and_version(selenium_nodesock):
    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tls_server(handler) as (host, port, ca_pem):
        result = _tls_run(
            selenium_nodesock,
            host,
            port,
            ca_pem,
            """
c = ss.cipher()
v = ss.version()
ss.sendall(b"ping")
ss.recv(1024)
ss.close()
(len(c) == 3, isinstance(c[0], str), "TLS" in v)
""",
        )

    assert result[0] is True, "cipher() should return a 3-tuple"
    assert result[1] is True, "cipher name should be a string"
    assert result[2] is True, "version() should contain 'TLS'"


@pytest.mark.skip_refcount_check
@only_node
def test_tls_getpeercert(selenium_nodesock):
    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tls_server(handler) as (host, port, ca_pem):
        result = _tls_run(
            selenium_nodesock,
            host,
            port,
            ca_pem,
            """
cert = ss.getpeercert()
ss.sendall(b"ping")
ss.recv(1024)
ss.close()
(type(cert).__name__, "subject" in cert if isinstance(cert, dict) else False)
""",
        )

    assert result[0] == "dict", f"Expected dict, got {result[0]}"
    assert result[1] is True, "Peer cert should have 'subject' key"


@pytest.mark.skip_refcount_check
@only_node
def test_tls_reject_unauthorized(selenium_nodesock):
    def handler(conn, _addr):
        conn.recv(1024)
        conn.sendall(b"OK")

    with tls_server(handler, expect_client_error=True) as (host, port, _ca_pem):
        result = selenium_nodesock.run_js(
            f"""
            return await pyodide.runPythonAsync(`
import socket
import ssl

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("{host}", {port}))

try:
    ss = ctx.wrap_socket(s, server_hostname="localhost")
    result = "no_error"
except Exception as e:
    result = type(e).__name__
finally:
    s.close()
result
            `);
            """
        )

    assert result != "no_error", "Expected TLS rejection, but got no error"


@pytest.mark.skip_refcount_check
@only_node
def test_tls_large_data(selenium_nodesock):
    DATA_SIZE = 64 * 1024

    def handler(conn, _addr):
        received = b""
        while len(received) < DATA_SIZE:
            chunk = conn.recv(8192)
            if not chunk:
                break
            received += chunk
        conn.sendall(f"Received {len(received)} bytes".encode())

    with tls_server(handler, timeout=10.0) as (host, port, ca_pem):
        result = _tls_run(
            selenium_nodesock,
            host,
            port,
            ca_pem,
            f"""
data = b"X" * {DATA_SIZE}
ss.sendall(data)
response = ss.recv(1024)
ss.close()
response.decode()
""",
        )

    assert result == f"Received {DATA_SIZE} bytes"
