import asyncio
import pathlib

import pytest
from pyodide_test_runner.decorator import run_in_pyodide

from pyodide import eval_code_async


def complicated_decorator(attr_name: str):
    def inner_func(value):
        def dec(func):
            def wrapper(*args, **kwargs):
                wrapper.dec_info.append((attr_name, value))
                return func(*args, **kwargs)

            wrapper.dec_info = getattr(func, "dec_info", [])
            wrapper.__name__ = func.__name__
            return wrapper

        return dec

    return inner_func


d1 = complicated_decorator("testdec1")
d2 = complicated_decorator("testdec2")


def test_web_server_secondary(selenium, web_server_secondary):
    host, port, logs = web_server_secondary
    assert pathlib.Path(logs).exists()
    assert selenium.server_port != port


@run_in_pyodide
def example_func1():
    x = 6
    y = 7
    assert x == y


run_in_pyodide_alias = run_in_pyodide()


@run_in_pyodide_alias
def example_func2():
    x = 6
    y = 7
    assert x == y


@run_in_pyodide
async def async_example_func():
    from asyncio import sleep

    await sleep(0.01)
    x = 6
    await sleep(0.01)
    y = 7
    assert x == y


@run_in_pyodide
@d1("a")
@d2("b")
@d1("c")
def example_decorator_func():
    pass


class selenium_mock:
    JavascriptException = Exception
    browser = "none"

    @staticmethod
    def load_package(*args, **kwargs):
        pass

    @staticmethod
    def run_async(code: str):
        return asyncio.new_event_loop().run_until_complete(eval_code_async(code))


def make_patched_fail(exc_list):
    def patched_fail(self, exc):
        exc_list.append(exc)

    return patched_fail


def check_err(exc_list, ty, msg):
    try:
        assert exc_list
        err = exc_list[0]
        assert err
        assert err.exc_type is AssertionError
        assert "".join(err.format_exception_only()) == msg
    finally:
        del exc_list[0]


def test_local1(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "fail", make_patched_fail(exc_list))

    example_func1(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_local2(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "fail", make_patched_fail(exc_list))

    example_func1(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_local3(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "fail", make_patched_fail(exc_list))

    async_example_func(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_local4():
    example_decorator_func(selenium_mock)
    assert example_decorator_func.dec_info == [
        ("testdec1", "a"),
        ("testdec2", "b"),
        ("testdec1", "c"),
    ]


def test_selenium(selenium, monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "fail", make_patched_fail(exc_list))

    example_func1(selenium)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")

    example_func2(selenium)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


@pytest.mark.parametrize("jinja2", ["jINja2", "Jinja2"])
@run_in_pyodide
def test_parametrize1(jinja2):
    assert jinja2.lower() == "jinja2"


@run_in_pyodide
@pytest.mark.parametrize("jinja2", ["jINja2", "Jinja2"])
def test_parametrize2(jinja2):
    assert jinja2.lower() == "jinja2"


@pytest.mark.skip(reason="Nope!")
@run_in_pyodide(pytest_assert_rewrites=False)
def test_skip1():
    x = 6
    assert x == 7


@run_in_pyodide(pytest_assert_rewrites=False)
@pytest.mark.skip(reason="Nope!")
def test_skip2():
    x = 6
    assert x == 7


@run_in_pyodide
async def test_run_in_pyodide_async():
    from asyncio import sleep

    x = 6
    await sleep(0.01)
    assert x == 6


import pickle
from zoneinfo import ZoneInfo

from hypothesis import HealthCheck, given, settings, strategies


def is_picklable(x):
    try:
        pickle.dumps(x)
        return True
    except Exception:
        return False


strategy = (
    strategies.from_type(type)
    .flatmap(strategies.from_type)
    .filter(lambda x: not isinstance(x, ZoneInfo))
    .filter(is_picklable)
)


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@given(obj=strategy)
@settings(
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=25,
)
@run_in_pyodide
def test_hypothesis(obj):
    from pyodide import to_js

    to_js(obj)
