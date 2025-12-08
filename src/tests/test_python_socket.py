import socket
import threading
import time

from pytest_pyodide import run_in_pyodide

from conftest import only_node


@only_node
def test_socket_connect(selenium):
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
    async def socket_client_test(selenium, port, message):
        import asyncio
        import socket

        # Create socket and connect
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))

        # Send data
        s.sendall(message)

        await asyncio.sleep(
            1
        )  # Yield control to event loop so that data can be processed

        # Receive response
        response = s.recv(1024)

        s.close()

        return response

    # Run the client test in Pyodide
    result = socket_client_test(selenium, PORT, TEST_MESSAGE)

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
