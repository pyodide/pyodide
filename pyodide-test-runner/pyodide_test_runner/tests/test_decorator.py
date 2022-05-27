import asyncio

import pytest
from pyodide_test_runner.decorator import run_in_pyodide
from pyodide_test_runner.utils import parse_driver_timeout

from pyodide import eval_code_async


@run_in_pyodide(_force_assert_rewrites=True)
def example_func1(selenium):
    x = 6
    y = 7
    assert x == y


run_in_pyodide_alias = run_in_pyodide(_force_assert_rewrites=True)


@run_in_pyodide_alias
def example_func2(selenium):
    x = 6
    y = 7
    assert x == y


run_in_pyodide_inner = run_in_pyodide()


@run_in_pyodide(_force_assert_rewrites=True)
async def async_example_func(selenium):
    from asyncio import sleep

    await sleep(0.01)
    x = 6
    await sleep(0.01)
    y = 7
    assert x == y


class selenium_mock:
    JavascriptException = Exception
    browser = "none"

    @staticmethod
    def load_package(*args, **kwargs):
        pass

    @staticmethod
    def run_async(code: str):
        return asyncio.new_event_loop().run_until_complete(eval_code_async(code))


def test_local1():
    with pytest.raises(AssertionError, match="assert 6 == 7"):
        example_func1(selenium_mock)


def test_local2():
    with pytest.raises(AssertionError, match="assert 6 == 7"):
        example_func2(selenium_mock)


def test_local3():
    with pytest.raises(AssertionError, match="assert 6 == 7"):
        async_example_func(selenium_mock)


def test_local_inner_function():
    @run_in_pyodide
    def inner_function(selenium, x):
        assert x == 6
        return 7

    inner_function(selenium_mock, 6)


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


@d1("a")
@d2("b")
@d1("c")
@run_in_pyodide
def example_decorator_func(selenium):
    pass


def test_local4():
    example_decorator_func(selenium_mock)
    assert example_decorator_func.dec_info == [
        ("testdec1", "a"),
        ("testdec2", "b"),
        ("testdec1", "c"),
    ]


class selenium_mock_fail_load_package(selenium_mock):
    @staticmethod
    def load_package(*args, **kwargs):
        raise OSError("STOP!")


def test_local_fail_load_package():
    exc = None
    try:
        example_func1(selenium_mock_fail_load_package)
    except OSError:
        exc = pytest.ExceptionInfo.from_current()

    assert exc
    try:
        exc.getrepr()
    except IndexError as e:
        import traceback

        traceback.print_exception(e)
        raise Exception(
            "run_in_pyodide decorator badly messed up the line numbers."
            " This could crash pytest. Printed the traceback to stdout."
        )


def test_selenium(selenium):
    with pytest.raises(AssertionError, match="assert 6 == 7"):
        example_func1(selenium)

    with pytest.raises(AssertionError, match="assert 6 == 7"):
        example_func2(selenium)


@run_in_pyodide
def test_trivial1(selenium):
    x = 7
    assert x == 7


@run_in_pyodide()
def test_trivial2(selenium):
    x = 7
    assert x == 7


@run_in_pyodide(pytest_assert_rewrites=False)
def test_trivial3(selenium):
    x = 7
    assert x == 7


@pytest.mark.parametrize("jinja2", ["jINja2", "Jinja2"])
@run_in_pyodide
def test_parametrize(selenium, jinja2):
    try:
        assert jinja2.lower() == "jinja2"
    except Exception as e:
        print(e)


@pytest.mark.skip(reason="Nope!")
@run_in_pyodide(pytest_assert_rewrites=False)
def test_skip(selenium):
    x = 6
    assert x == 7


@run_in_pyodide
async def test_run_in_pyodide_async(selenium):
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
def test_hypothesis(selenium, obj):
    from pyodide import to_js

    to_js(obj)


run_in_pyodide_alias2 = pytest.mark.driver_timeout(40)(run_in_pyodide_inner)


@run_in_pyodide_alias2
def test_run_in_pyodide_alias(request):
    assert parse_driver_timeout(request.node) == 40
