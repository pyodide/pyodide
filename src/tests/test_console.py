import asyncio
import re
import sys
import time

import pytest
from pytest_pyodide import run_in_pyodide

from pyodide import console
from pyodide.code import CodeRunner  # noqa: E402
from pyodide.console import Console, _CommandCompiler, _Compile  # noqa: E402


def test_command_compiler():
    c = _Compile()
    with pytest.raises(SyntaxError, match="(invalid syntax|incomplete input)"):
        c("def test():\n   1", "<input>", "single")
    assert isinstance(c("def test():\n   1\n", "<input>", "single"), CodeRunner)
    with pytest.raises(SyntaxError, match="invalid syntax"):
        c("1<>2", "<input>", "single")
    assert isinstance(
        c("from __future__ import barry_as_FLUFL", "<input>", "single"), CodeRunner
    )
    assert isinstance(c("1<>2", "<input>", "single"), CodeRunner)

    c2 = _CommandCompiler()
    assert c2("def test():\n   1", "<input>", "single") is None
    assert isinstance(c2("def test():\n   1\n", "<input>", "single"), CodeRunner)
    with pytest.raises(SyntaxError, match="(invalid syntax|incomplete input)"):
        c2("1<>2", "<input>", "single")
    assert isinstance(
        c2("from __future__ import barry_as_FLUFL", "<input>", "single"), CodeRunner
    )
    assert isinstance(c2("1<>2", "<input>", "single"), CodeRunner)


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
    for string in ("x" * 10**5, "x" * (10**5 + 1)):
        for limit in (9, 10, 100, 101):
            assert len(
                console.repr_shorten(string, limit=limit, separator=sep)
            ) == 2 * (limit // 2) + len(sep)


def test_completion():
    shell = Console({"a_variable": 7})
    assert shell.complete("a") == (
        [
            "and ",
            "as ",
            "assert ",
            "async ",
            "await ",
            "a_variable",
            "abs(",
            "all(",
            "any(",
            "ascii(",
            "aiter(",
            "anext(",
        ],
        0,
    )

    assert shell.complete("a = 0 ; print.__g") == (
        [
            "print.__ge__(",
            "print.__getattribute__(",
            "print.__getstate__()",
            "print.__gt__(",
        ],
        8,
    )


def test_interactive_console():
    shell = Console()

    def assert_incomplete(input):
        res = shell.push(input)
        assert res.syntax_check == "incomplete"

    async def get_result(input):
        res = shell.push(input)
        assert res.syntax_check == "complete"
        return await res

    async def test():
        assert await get_result("x = 5") is None
        assert await get_result("x") == 5
        assert await get_result("x ** 2") == 25

        assert_incomplete("def f(x):")
        assert_incomplete("    return x*x + 1")
        assert await get_result("") is None
        assert await get_result("[f(x) for x in range(5)]") == [1, 2, 5, 10, 17]

        assert_incomplete("def factorial(n):")
        assert_incomplete("    if n < 2:")
        assert_incomplete("        return 1")
        assert_incomplete("    else:")
        assert_incomplete("        return n * factorial(n - 1)")
        assert await get_result("") is None
        assert await get_result("factorial(10)") == 3628800

        assert await get_result("import pytz") is None
        assert await get_result("pytz.utc.zone") == "UTC"

        fut = shell.push("1+")
        assert fut.syntax_check == "syntax-error"
        assert fut.exception() is not None

        err = fut.formatted_error or ""
        err = re.sub(r"SyntaxError: .+", "SyntaxError: <errormsg>", err).strip()
        assert [e.strip() for e in err.split("\n")] == [
            'File "<console>", line 1',
            "1+",
            "^",
            "SyntaxError: <errormsg>",
        ]

        fut = shell.push("raise Exception('hi')")
        try:
            await fut
        except Exception:
            assert (
                fut.formatted_error
                == 'Traceback (most recent call last):\n  File "<console>", line 1, in <module>\nException: hi\n'
            )

    asyncio.run(test())


def test_top_level_await():
    from asyncio import Queue, sleep

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    q: Queue[int] = Queue()
    shell = Console(locals())
    fut = shell.push("await q.get()")

    async def test():
        await sleep(0.3)
        assert not fut.done()
        await q.put(5)
        assert await fut == 5

    loop.run_until_complete(test())


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
        assert res.syntax_check == "complete"
        return await res

    async def test():
        assert await get_result("print('foobar')") is None
        assert my_stdout == "foo\nfoobar\n"

        assert await get_result("print('foobar')") is None
        assert my_stdout == "foo\nfoobar\nfoobar\n"

        assert await get_result("1+1") == 2
        assert my_stdout == "foo\nfoobar\nfoobar\n"

    asyncio.run(test())

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

    def stdin_callback(n: int) -> str:
        return ""

    def stdout_callback(string: str) -> None:
        nonlocal my_stdout
        my_stdout += string

    def stderr_callback(string: str) -> None:
        nonlocal my_stderr
        my_stderr += string

    async def get_result(input):
        res = shell.push(input)
        assert res.syntax_check == "complete"
        return await res

    shell = Console(
        stdin_callback=stdin_callback,
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=False,
    )

    print("foo")
    assert my_stdout == ""

    async def test():
        assert await get_result("print('foobar')") is None
        assert my_stdout == "foobar\n"

        print("bar")
        assert my_stdout == "foobar\n"

        assert await get_result("print('foobar')") is None
        assert my_stdout == "foobar\nfoobar\n"

        assert await get_result("import sys") is None
        assert await get_result("print('foobar', file=sys.stderr)") is None
        assert my_stderr == "foobar\n"

        assert await get_result("1+1") == 2

        assert await get_result("sys.stdin.isatty()")
        assert await get_result("sys.stdout.isatty()")
        assert await get_result("sys.stderr.isatty()")

    asyncio.run(test())


@pytest.mark.skip_refcount_check
@run_in_pyodide
async def test_console_imports(selenium):
    from pyodide.console import PyodideConsole

    shell = PyodideConsole()

    async def get_result(input):
        res = shell.push(input)
        assert res.syntax_check == "complete"
        return await res

    assert await get_result("import pytz") is None
    assert await get_result("pytz.utc.zone") == "UTC"


@pytest.mark.xfail_browsers(node="Not available in node")
def test_console_html(selenium):
    selenium.goto(
        f"http://{selenium.server_hostname}:{selenium.server_port}/console.html"
    )
    selenium.javascript_setup()
    selenium.run_js(
        """
        await window.console_ready;
        """
    )

    def term_exec(x):
        return selenium.run_js(
            f"""
            await term.ready;
            term.clear();
            let x={x!r};
            for(let t of x.split("\\n")){{
                await term.ready;
                term.exec(t);
            }}
            """
        )

    def get_result():
        return selenium.run_js(
            """
            await term.ready;
            return term.get_output().trim();
            """
        )

    def exec_and_get_result(x):
        term_exec(x)
        return get_result()

    welcome_msg = "Welcome to the Pyodide terminal emulator 🐍"
    output = selenium.run_js("return term.get_output()")
    cleaned = re.sub("Pyodide [0-9a-z.]*", "Pyodide", output)
    assert cleaned[: len(welcome_msg)] == welcome_msg

    assert exec_and_get_result("1+1") == ">>> 1+1\n2"
    assert exec_and_get_result("1 +1") == ">>> 1 +1\n2"
    assert exec_and_get_result("1+ 1") == ">>> 1+ 1\n2"
    assert exec_and_get_result("[1,2,3]") == ">>> [1,2,3]\n[1, 2, 3]"
    assert (
        exec_and_get_result("{'a' : 1, 'b' : 2, 'c' : 3}")
        == ">>> {'a' : 1, 'b' : 2, 'c' : 3}\n{'a': 1, 'b': 2, 'c': 3}"
    )
    assert (
        exec_and_get_result("{'a': {'b': 1}}") == ">>> {'a': {'b': 1}}\n{'a': {'b': 1}}"
    )
    assert (
        exec_and_get_result("[x*x+1 for x in range(5)]")
        == ">>> [x*x+1 for x in range(5)]\n[1, 2, 5, 10, 17]"
    )
    assert (
        exec_and_get_result("{x+1:x*x+1 for x in range(5)}")
        == ">>> {x+1:x*x+1 for x in range(5)}\n{1: 1, 2: 2, 3: 5, 4: 10, 5: 17}"
    )
    assert (
        exec_and_get_result("print('\x1b[31mHello World\x1b[0m')")
        == ">>> print('[[;#A00;]Hello World]')\n[[;#A00;]Hello World]"
    )

    term_exec(
        """
        async def f():
            return 7
        """
    )

    assert re.search("<coroutine object f at 0x[a-f0-9]*>", exec_and_get_result("f()"))

    from textwrap import dedent

    print(exec_and_get_result("1+"))

    assert (
        exec_and_get_result("1+")
        == dedent(
            """
            >>> 1+
            [[;;;terminal-error]  File \"<console>\", line 1
                1+
                 ^
            SyntaxError: incomplete input]
            """
        ).strip()
    )

    assert (
        exec_and_get_result("raise Exception('hi')")
        == dedent(
            """
            >>> raise Exception('hi')
            [[;;;terminal-error]Traceback (most recent call last):
              File \"<console>\", line 1, in <module>
            Exception: hi]
            """
        ).strip()
    )

    result = exec_and_get_result(
        dedent(
            """
            class Test:
                def __repr__(self):
                    raise TypeError("hi")

            Test()
            """
        ).strip()
    )
    result = re.sub(r"line \d+, in repr_shorten", "line xxx, in repr_shorten", result)
    result = re.sub(r"/lib/python.+?/", "/lib/pythonxxx/", result)

    answer = dedent(
        """
            >>> class Test:
            ...     def __repr__(self):
            ...         raise TypeError(\"hi\")
            ... \

            >>> Test()
            [[;;;terminal-error]Traceback (most recent call last):
              File \"/lib/pythonxxx/pyodide/console.py\", line xxx, in repr_shorten
                text = repr(value)
                       ^^^^^^^^^^^
              File \"<console>\", line 3, in __repr__
            TypeError: hi]
            """
    ).strip()

    assert result == answer

    long_output = exec_and_get_result("list(range(1000))").split("\n")
    assert len(long_output) == 4
    assert long_output[2] == "<long output truncated>"

    # nbsp characters should be replaced with spaces, and not cause a syntax error
    nbsp = "1\xa0\xa0\xa0+\xa0\xa01"
    assert "SyntaxError" not in exec_and_get_result(nbsp)

    term_exec("from _pyodide_core import trigger_fatal_error; trigger_fatal_error()")
    time.sleep(0.3)
    res = selenium.run_js("return term.get_output().trim();")
    assert (
        res
        == dedent(
            """
            >>> from _pyodide_core import trigger_fatal_error; trigger_fatal_error()
            [[;;;terminal-error]Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.]
            [[;;;terminal-error]The cause of the fatal error was:]
            [[;;;terminal-error]Error: intentionally triggered fatal error!]
            [[;;;terminal-error]Look in the browser console for more details.]
            """
        ).strip()
    )
