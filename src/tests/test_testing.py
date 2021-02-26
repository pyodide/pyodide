import pathlib
from pyodide_build.testing import run_in_pyodide


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


@run_in_pyodide
def test_run_in_pyodide():
    pass
