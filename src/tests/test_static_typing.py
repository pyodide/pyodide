from inspect import getsource
from pathlib import Path
from textwrap import dedent
from typing import TypeVar, assert_type

from mypy.api import run
from pytest import raises


def _mypy_check(source: str) -> tuple[str, str, int]:
    path = str(Path(__file__).parent.parent.parent / "pyproject.toml")
    stdout, stderr, exit_status = run(["-c", source, "--config-file", path])
    return stdout, stderr, exit_status


def assert_no_error(source: str) -> None:
    stdout, _, exit_status = _mypy_check(f"from typing import *\n\n{dedent(source)}")
    assert exit_status == 0, stdout


def test_self():
    with raises(AssertionError):
        assert_no_error("a: str = 123")


def test_create_proxy():
    def _():
        from pyodide.ffi import create_proxy

        a: int = 2
        assert_type(create_proxy(a).unwrap(), int)

    assert_no_error(getsource(_))


def test_generic():
    def _():
        from pyodide.ffi import JsDoubleProxy, JsPromise

        def _(a: JsPromise[int]) -> None:
            assert_type(a.then(str), JsPromise[str])

        def _(b: JsDoubleProxy[str]) -> None:
            assert_type(b.unwrap(), str)

    assert_no_error(getsource(_))


def test_callable_generic():
    def _():
        from pyodide.ffi import create_once_callable, create_proxy

        T = TypeVar("T", int, float, str)

        def f(x: T) -> T:
            return x * 2

        assert_type(create_once_callable(f)(2), int)
        assert_type(create_proxy(f)(""), str)

    assert_no_error(getsource(_))


def test_decorator_usage():
    def _():
        from pyodide.ffi import create_once_callable

        T = TypeVar("T")

        @create_once_callable
        def f(x: T) -> list[T]:
            return [x]

        assert_type(f((int(input()), str(input()))), list[tuple[int, str]])

    assert_no_error(getsource(_))
