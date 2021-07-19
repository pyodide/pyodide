import asyncio
import pytest
from pathlib import Path
import sys

from pyodide_build.testing import run_in_pyodide
from conftest import selenium_common

sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "py"))

from pyodide import console, CodeRunner  # noqa: E402
from pyodide.console import (
    Console,
    _CodeRunnerCompile,
    _CodeRunnerCommandCompiler,
)  # noqa: E402


def test_command_compiler():
    c = _CodeRunnerCompile()
    with pytest.raises(SyntaxError, match="unexpected EOF while parsing"):
        c("def test():\n   1", "<input>", "single")
    assert isinstance(c("def test():\n   1\n", "<input>", "single"), CodeRunner)
    with pytest.raises(SyntaxError, match="invalid syntax"):
        c("1<>2", "<input>", "single")
    assert isinstance(
        c("from __future__ import barry_as_FLUFL", "<input>", "single"), CodeRunner
    )
    assert isinstance(c("1<>2", "<input>", "single"), CodeRunner)

    c = _CodeRunnerCommandCompiler()
    assert c("def test():\n   1", "<input>", "single") is None
    assert isinstance(c("def test():\n   1\n", "<input>", "single"), CodeRunner)
    with pytest.raises(SyntaxError, match="invalid syntax"):
        c("1<>2", "<input>", "single")
    assert isinstance(
        c("from __future__ import barry_as_FLUFL", "<input>", "single"), CodeRunner
    )
    assert isinstance(c("1<>2", "<input>", "single"), CodeRunner)


def test_write_stream():
    my_buffer = ""

    def callback(string):
        nonlocal my_buffer
        my_buffer += string

    my_stream = console._WriteStream(callback)

    print("foo", file=my_stream)
    assert my_buffer == "foo\n"
    print("bar", file=my_stream)
    assert my_buffer == "foo\nbar\n"


def test_repr():
    sep = "..."
    for string in ("x" * 10 ** 5, "x" * (10 ** 5 + 1)):
        for limit in (9, 10, 100, 101):
            assert len(
                console.repr_shorten(string, limit=limit, separator=sep)
            ) == 2 * (limit // 2) + len(sep)


def test_completion():
    shell = Console({"a_variable": 7})
    shell.complete("a") == (
        [
            "and ",
            "as ",
            "assert ",
            "async ",
            "await ",
            "abs(",
            "all(",
            "any(",
            "ascii(",
            "a_variable",
        ],
        0,
    )

    assert shell.complete("a = 0 ; print.__g") == (
        [
            "print.__ge__(",
            "print.__getattribute__(",
            "print.__gt__(",
        ],
        8,
    )


async def test_interactive_console():
    shell = Console()

    def assert_incomplete(input):
        res = shell.push(input)
        assert res == ("incomplete", None)

    async def get_result(input):
        res = shell.push(input)
        [status, fut] = res
        assert status == "complete"
        [status, value] = await fut
        assert status == "success"
        return value

    assert await get_result("x = 5") == None
    assert await get_result("x") == 5
    assert await get_result("x ** 2") == 25

    assert_incomplete("def f(x):")
    assert_incomplete("    return x*x + 1")
    assert await get_result("") == None
    assert await get_result("[f(x) for x in range(5)]") == [1, 2, 5, 10, 17]

    assert_incomplete("def factorial(n):")
    assert_incomplete("    if n < 2:")
    assert_incomplete("        return 1")
    assert_incomplete("    else:")
    assert_incomplete("        return n * factorial(n - 1)")
    assert await get_result("") == None
    assert await get_result("factorial(10)") == 3628800

    assert await get_result("import pytz") == None
    assert await get_result("pytz.utc.zone") == "UTC"

    [status, val] = shell.push("1+")
    assert status == "syntax-error"
    assert (
        val
        == '  File "<console>", line 1\n    1+\n      ^\nSyntaxError: invalid syntax\n'
    )

    [state, fut] = shell.push("raise Exception('hi')")
    assert state == "complete"
    assert await fut == (
        "exception",
        'Traceback (most recent call last):\n  File "<console>", line 1, in <module>\nException: hi\n',
    )


def test_top_level_await():
    from asyncio import Queue, sleep, get_event_loop

    q = Queue()
    shell = Console(locals())
    (_, fut) = shell.push("await q.get()")

    async def test():
        await sleep(0.3)
        assert not fut.done()
        await q.put(5)
        assert await fut == ("success", 5)

    get_event_loop().run_until_complete(test())


@pytest.fixture
def safe_sys_redirections():
    redirected = sys.stdout, sys.stderr, sys.displayhook
    try:
        yield
    finally:
        sys.stdout, sys.stderr, sys.displayhook = redirected


def test_persistent_redirection(safe_sys_redirections):
    my_stdout = ""
    my_stderr = ""
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    def stdout_callback(string):
        nonlocal my_stdout
        my_stdout += string

    def stderr_callback(string):
        nonlocal my_stderr
        my_stderr += string

    shell = Console(
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=True,
    )

    # std names
    assert sys.stdout.name == orig_stdout.name
    assert sys.stderr.name == orig_stderr.name

    # std redirections
    print("foo")
    assert my_stdout == "foo\n"
    print("bar", file=sys.stderr)
    assert my_stderr == "bar\n"
    my_stderr = ""

    async def get_result(input):
        res = shell.push(input)
        [status, fut] = res
        assert status == "complete"
        [status, value] = await fut
        assert status == "success"
        return value

    async def test():
        assert await get_result("print('foobar')") == None
        assert my_stdout == "foo\nfoobar\n"

        assert await get_result("print('foobar')") == None
        assert my_stdout == "foo\nfoobar\nfoobar\n"

        assert await get_result("1+1") == 2
        assert my_stdout == "foo\nfoobar\nfoobar\n"

    asyncio.get_event_loop().run_until_complete(test())

    my_stderr = ""

    shell.persistent_restore_streams()
    my_stdout = ""
    my_stderr = ""
    print(sys.stdout, file=orig_stdout)
    print("bar")
    assert my_stdout == ""

    print("foo", file=sys.stdout)
    assert my_stderr == ""


def test_nonpersistent_redirection(safe_sys_redirections):
    my_stdout = ""
    my_stderr = ""

    def stdout_callback(string):
        nonlocal my_stdout
        my_stdout += string

    def stderr_callback(string):
        nonlocal my_stderr
        my_stderr += string

    async def get_result(input):
        res = shell.push(input)
        [status, fut] = res
        assert status == "complete"
        [status, value] = await fut
        assert status == "success"
        return value

    shell = Console(
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=False,
    )

    print("foo")
    assert my_stdout == ""

    async def test():
        assert await get_result("print('foobar')") == None
        assert my_stdout == "foobar\n"

        print("bar")
        assert my_stdout == "foobar\n"

        assert await get_result("print('foobar')") == None
        assert my_stdout == "foobar\nfoobar\n"

        assert await get_result("import sys") == None
        assert await get_result("print('foobar', file=sys.stderr)") == None
        assert my_stderr == "foobar\n"

        assert await get_result("1+1") == 2

    asyncio.get_event_loop().run_until_complete(test())


@pytest.mark.skip_refcount_check
@run_in_pyodide
async def test_console_imports():
    from pyodide.console import PyodideConsole

    shell = PyodideConsole()

    async def get_result(input):
        res = shell.push(input)
        [status, fut] = res
        assert status == "complete"
        [status, value] = await fut
        assert status == "success"
        return value

    assert await get_result("import pytz") == None
    assert await get_result("pytz.utc.zone") == "UTC"


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def console_html_fixture(request, web_server_main):
    with selenium_common(request, web_server_main, False) as selenium:
        selenium.driver.get(
            f"http://{selenium.server_hostname}:{selenium.server_port}/console.html"
        )
        selenium.javascript_setup()
        try:
            yield selenium
        finally:
            print(selenium.logs)


def test_console_html(console_html_fixture):
    selenium = console_html_fixture
    selenium.run_js(
        """
        await window.console_ready;
        """
    )
    result = selenium.run_js(
        r"""
        let result = [];
        assert(() => term.get_output().startsWith("Welcome to the Pyodide terminal emulator 🐍"))

        term.clear();
        term.exec("1+1");
        await term.ready;
        assert(() => term.get_output().trim() === ">>> 1+1\n2", term.get_output().trim());


        term.clear();
        term.exec("1+");
        await term.ready;
        result.push([term.get_output(),
`>>> 1+
[[;;;terminal-error]  File "<console>", line 1
    1+
      ^
SyntaxError: invalid syntax]`
        ]);

        term.clear();
        term.exec("raise Exception('hi')");
        await term.ready;
        result.push([term.get_output(),
`>>> raise Exception('hi')
[[;;;terminal-error]Traceback (most recent call last):
  File "<console>", line 1, in <module>
Exception: hi]`
        ]);

        term.clear();
        term.exec("from _pyodide_core import trigger_fatal_error; trigger_fatal_error()");
        await sleep(100);
        result.push([term.get_output(),
`>>> from _pyodide_core import trigger_fatal_error; trigger_fatal_error()
[[;;;terminal-error]Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.]
[[;;;terminal-error]The cause of the fatal error was:]
[[;;;terminal-error]Error: intentionally triggered fatal error!]
[[;;;terminal-error]Look in the browser console for more details.]`
        ]);

        assert(() => term.paused());
        return result;
        """
    )
    for [x, y] in result:
        assert x == y
