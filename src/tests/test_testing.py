import pathlib
import pytest


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


def assert_C_test(result):
    print("result:", repr(result))
    if result:
        raise AssertionError(result)


def test_C_test_entrypoints(selenium):
    assert selenium.run_js("return pyodide.Tests.test_entrypoints() === 'It works!';")


def test_C_tests_succeed1(selenium):
    assert_C_test(
        selenium.run_js("return pyodide.Tests.c_tests_expect_success_success();")
    )


def test_C_tests_succeed2(selenium):
    assert_C_test(selenium.run_js("return pyodide.Tests.c_tests_expect_fail_fail();"))


def test_C_tests_fail1(selenium):
    msg = "Assertion failed on line"
    with pytest.raises(AssertionError, match=msg):
        assert_C_test(
            selenium.run_js("return pyodide.Tests.c_tests_expect_success_fails();")
        )


def test_C_tests_fail2(selenium):
    msg = "Expected an assertion failure, but all assertions passed."
    with pytest.raises(AssertionError, match=msg):
        assert_C_test(
            selenium.run_js("return pyodide.Tests.c_tests_expect_fail_succeeds();")
        )


def test_C_tests_fail3(selenium):
    msg = 'Expected an assertion failure matching pattern "77".'
    with pytest.raises(AssertionError, match=msg):
        assert_C_test(
            selenium.run_js("return pyodide.Tests.c_tests_expect_fail_wrong_message();")
        )
