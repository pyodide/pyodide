import pytest
from pathlib import Path
import sys

from conftest import selenium_common

sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "py"))

from pyodide import console  # noqa: E402


def test_stream_redirection():
    my_buffer = ""

    def callback(string):
        nonlocal my_buffer
        my_buffer += string

    my_stream = console._WriteStream(callback)

    print("foo", file=my_stream)
    assert my_buffer == "foo\n"
    print("bar", file=my_stream)
    assert my_buffer == "foo\nbar\n"


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

    [state, res] = shell.push("print('foobar')")
    assert state == "valid"
    assert res.result() == ["success", None]
    assert my_stdout == "foo\nfoobar\n"

    [state, res] = shell.push("print('foobar')")
    assert state == "valid"
    assert res.result() == ["success", None]
    assert my_stdout == "foo\nfoobar\nfoobar\n"

    [state, res] = shell.push("1+1")
    assert state == "valid"
    assert res.result() == ["success", 2]
    assert my_stdout == "foo\nfoobar\nfoobar\n"

    my_stderr = ""
    [state, res] = shell.push("raise Exception('hi')")
    assert state == "valid"
    # assert res.result() == ["exception", 'Traceback (most recent call last):\n  File "<console>", line 1, in <module>\nException: hi\n']
    # assert shell.run_complete.exception() is not None
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

    shell = console.InteractiveConsole(
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=False,
    )

    print("foo")
    assert my_stdout == ""

    shell.push("print('foobar')")
    assert my_stdout == "foobar\n"

    print("bar")
    assert my_stdout == "foobar\n"

    shell.push("print('foobar')")
    assert my_stdout == "foobar\nfoobar\n"

    shell.push("import sys")
    shell.push("print('foobar', file=sys.stderr)")
    assert my_stderr == "foobar\n"

    [state, res] = shell.push("1+1")
    assert state == "valid"
    assert res.result() == ["success", 2]


def test_repr(safe_sys_redirections):
    sep = "..."
    for string in ("x" * 10 ** 5, "x" * (10 ** 5 + 1)):
        for limit in (9, 10, 100, 101):
            assert len(
                console.repr_shorten(string, limit=limit, separator=sep)
            ) == 2 * (limit // 2) + len(sep)


@pytest.fixture
def safe_selenium_sys_redirections(selenium):
    # Import console early since it makes three global hiwire allocations, and we don't want to anger
    # the memory leak checker
    selenium.run_js("pyodide._module.runPythonSimple(`from pyodide import console`)")

    selenium.run_js(
        "pyodide._module.runPythonSimple(`import sys; _redirected = sys.stdout, sys.stderr, sys.displayhook`)"
    )
    try:
        yield
    finally:
        selenium.run_js(
            "pyodide._module.runPythonSimple(`sys.stdout, sys.stderr, sys.displayhook = _redirected`)"
        )


def test_interactive_console(selenium, safe_selenium_sys_redirections):
    selenium.run(
        """
        import sys
        from pyodide.console import InteractiveConsole

        result = None

        def display(value):
            global result
            result = value

        shell = InteractiveConsole()
        shell.display = display

        def assert_incomplete(res):
            assert res == ["incomplete", None]

        async def assert_result(res, x):
            [status, fut] = res
            assert status == "valid"
            [status, value] = await fut
            print(status, value)
            assert status == "success"
            assert value == x
        """
    )

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            await assert_result(shell.push('x = 5'), None)
            await assert_result(shell.push('x'), 5)
            await assert_result(shell.push('x ** 2'), 25)

            assert_incomplete(shell.push('def f(x):'))
            assert_incomplete(shell.push('    return x*x + 1'))
            await assert_result(shell.push(''), None)
            await assert_result(shell.push('[f(x) for x in range(5)]'), [1, 2, 5, 10, 17])

            assert_incomplete(shell.push('def factorial(n):'))
            assert_incomplete(shell.push('    if n < 2:'))
            assert_incomplete(shell.push('        return 1'))
            assert_incomplete(shell.push('    else:'))
            assert_incomplete(shell.push('        return n * factorial(n - 1)'))
            await assert_result(shell.push(''), None)
            await assert_result(shell.push('factorial(10)'), 3628800)

            await assert_result(shell.push('import pytz'), None)
            await assert_result(shell.push('pytz.utc.zone'), "UTC")
        `)
        """
    )


def test_completion(selenium, safe_selenium_sys_redirections):
    selenium.run(
        """
        from pyodide import console

        shell = console.InteractiveConsole()
        """
    )

    assert selenium.run(
        """
        [completions, start] = shell.complete('a')
        [tuple(completions), start]
        """
    ) == [
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
        ],
        0,
    ]

    assert selenium.run(
        """
        [completions, start] = shell.complete('a = 0 ; print.__g')
        [tuple(completions), start]
        """
    ) == [
        [
            "print.__ge__(",
            "print.__getattribute__(",
            "print.__gt__(",
        ],
        8,
    ]


def test_interactive_console_top_level_await(selenium, safe_selenium_sys_redirections):
    selenium.run(
        """
        import sys
        from pyodide.console import InteractiveConsole

        result = None

        def display(value):
            global result
            result = value

        shell = InteractiveConsole()
        shell.display = display
        """
    )
    selenium.run("shell.push('from js import fetch')")
    selenium.run("shell.push('await (await fetch(`packages.json`)).json()')")
    assert selenium.run("result") == None


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
