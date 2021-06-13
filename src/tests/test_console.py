import pytest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "py"))

from pyodide import console  # noqa: E402


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
    from pyodide import console

    shell = console.InteractiveConsole({"a_variable": 7})
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


def test_interactive_console():
    from pyodide.console import InteractiveConsole

    shell = InteractiveConsole()

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

    async def test():
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
            == '  File "<console>", line 1\n    1+\n     ^\nSyntaxError: invalid syntax\n'
        )

        [state, fut] = shell.push("raise Exception('hi')")
        assert state == "complete"
        assert await fut == (
            "exception",
            'Traceback (most recent call last):\n  File "<console>", line 1, in <module>\nException: hi\n',
        )

    import asyncio

    asyncio.get_event_loop().run_until_complete(test())


def test_top_level_await():
    from asyncio import Queue, sleep, get_event_loop
    from pyodide.console import InteractiveConsole

    q = Queue()
    shell = InteractiveConsole(locals())
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

    shell = console.InteractiveConsole(
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

    import asyncio

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

    shell = console.InteractiveConsole(
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

    import asyncio

    asyncio.get_event_loop().run_until_complete(test())
