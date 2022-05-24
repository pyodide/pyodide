import asyncio

from pyodide_test_runner.decorator import run_in_pyodide

from pyodide import eval_code_async


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
        assert "".join(err.format_exception_only()) == msg
    finally:
        del exc_list[0]


def test_local1(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "_fail", make_patched_fail(exc_list))

    example_func1(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_local2(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "_fail", make_patched_fail(exc_list))

    example_func1(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_local3(monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "_fail", make_patched_fail(exc_list))

    async_example_func(selenium_mock)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


def test_selenium(selenium, monkeypatch):
    exc_list = []
    monkeypatch.setattr(run_in_pyodide, "_fail", make_patched_fail(exc_list))

    example_func1(selenium)

    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")

    example_func2(selenium)
    check_err(exc_list, AssertionError, "AssertionError: assert 6 == 7\n")


@run_in_pyodide
def test_trivial1():
    x = 7
    assert x == 7


@run_in_pyodide()
def test_trivial2():
    x = 7
    assert x == 7


@run_in_pyodide(pytest_assert_rewrites=False)
def test_trivial3():
    x = 7
    assert x == 7


@run_in_pyodide
async def test_run_in_pyodide_async():
    from asyncio import sleep

    x = 6
    await sleep(0.01)
    assert x == 6
