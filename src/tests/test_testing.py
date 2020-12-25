import pathlib
import pytest
from selenium.common.exceptions import WebDriverException


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


def test_C_test_entrypoints(selenium):
    assert selenium.run_js("return pyodide.Tests.test_entrypoints() === 'It works!';")


def test_C_tests(selenium):
    selenium.run_js("pyodide.Tests.test_c_tests_success()")
    msg = r"Assertion failed on line [0-9]* in src/main.c"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run_js("pyodide.Tests.test_c_tests_fail()")
