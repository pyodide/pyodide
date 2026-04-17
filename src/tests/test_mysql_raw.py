import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node

pytestmark = [
    pytest.mark.requires_dynamic_linking,
    only_node,
]


@pytest.fixture(scope="function")
def selenium_nodesock(selenium_standalone_refresh, runtime):
    if runtime != "node":
        pytest.skip("Only works in node")
    selenium = selenium_standalone_refresh
    selenium.run_js("await pyodide.useNodeSockFS();")
    yield selenium


def test_recv_after_settimeout_none(selenium_nodesock):
    @run_in_pyodide
    def run(selenium):
        import socket

        s = socket.create_connection(("127.0.0.1", 3306), timeout=10)
        s.settimeout(None)
        data = s.recv(1024)
        s.close()
        return f"recv len={len(data)}"

    result = run(selenium_nodesock)
    print(f"Result: {result}")
    assert "len=0" not in result


def test_makefile_read_after_settimeout_none(selenium_nodesock):
    @run_in_pyodide
    def run(selenium):
        import socket

        s = socket.create_connection(("127.0.0.1", 3306), timeout=10)
        s.settimeout(None)
        rfile = s.makefile("rb")
        data = rfile.read(4)
        s.close()
        return f"makefile len={len(data)} hex={data.hex() if data else 'empty'}"

    result = run(selenium_nodesock)
    print(f"Result: {result}")
    assert "len=0" not in result


def test_makefile_read_no_settimeout(selenium_nodesock):
    @run_in_pyodide
    def run(selenium):
        import socket

        s = socket.create_connection(("127.0.0.1", 3306), timeout=10)
        # no settimeout(None) call
        rfile = s.makefile("rb")
        data = rfile.read(4)
        s.close()
        return f"makefile len={len(data)} hex={data.hex() if data else 'empty'}"

    result = run(selenium_nodesock)
    print(f"Result: {result}")
    assert "len=0" not in result
