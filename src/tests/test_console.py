import pytest
from pathlib import Path
import sys

from conftest import selenium_common

sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "py"))

from pyodide import console, CodeRunner  # noqa: E402
from pyodide.console import _CodeRunnerCompile, _CodeRunnerCommandCompiler  # noqa: E402


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


def test_interactive_console_streams(safe_sys_redirections):
    my_stdout = ""
    my_stderr = ""
    orig_sys_stdout_name = sys.stdout.name
    orig_sys_stderr_name = sys.stderr.name

    def stdout_callback(string):
        nonlocal my_stdout
        my_stdout += string

    def stderr_callback(string):
        nonlocal my_stderr
        my_stderr += string

    ##########################
    # Persistent redirection #
    ##########################
    shell = console._InteractiveConsole(
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=True,
    )

    # std names
    assert sys.stdout.name == orig_sys_stdout_name
    assert sys.stderr.name == orig_sys_stderr_name

    # std redirections
    print("foo")
    assert my_stdout == "foo\n"
    print("bar", file=sys.stderr)
    assert my_stderr == "bar\n"

    shell.push("print('foobar')")
    assert my_stdout == "foo\nfoobar\n"

    shell.push("print('foobar')")
    assert my_stdout == "foo\nfoobar\nfoobar\n"

    shell.push("1+1")
    assert my_stdout == "foo\nfoobar\nfoobar\n2\n"
    assert shell.run_complete.result() == 2

    my_stderr = ""
    shell.push("raise Exception('hi')")
    assert (
        my_stderr
        == 'Traceback (most recent call last):\n  File "<console>", line 1, in <module>\nException: hi\n'
    )
    assert shell.run_complete.exception() is not None
    my_stderr = ""
    shell.push("1+1")
    assert my_stderr == ""
    assert shell.run_complete.result() == 2

    del shell
    import gc

    gc.collect()

    my_stdout = ""
    my_stderr = ""

    print("bar")
    assert my_stdout == ""

    print("foo", file=sys.stdout)
    assert my_stderr == ""

    ##############################
    # Non persistent redirection #
    ##############################
    shell = console._InteractiveConsole(
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

    shell.push("1+1")
    assert my_stdout == "foobar\nfoobar\n2\n"


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
        from pyodide.console import _InteractiveConsole

        result = None

        def display(value):
            global result
            result = value

        shell = _InteractiveConsole()
        shell.display = display
        """
    )

    selenium.run("shell.push('x = 5')")
    selenium.run("shell.push('x')")
    selenium.run_js("await pyodide.runPythonAsync('await shell.run_complete');")
    assert selenium.run("result") == 5

    selenium.run("shell.push('x ** 2')")
    selenium.run_js("await pyodide.runPythonAsync('await shell.run_complete');")

    assert selenium.run("result") == 25

    selenium.run("shell.push('def f(x):')")
    selenium.run("shell.push('    return x*x + 1')")
    selenium.run("shell.push('')")
    selenium.run("shell.push('str([f(x) for x in range(5)])')")
    selenium.run_js("await pyodide.runPythonAsync('await shell.run_complete');")
    assert selenium.run("result") == str([1, 2, 5, 10, 17])

    selenium.run("shell.push('def factorial(n):')")
    selenium.run("shell.push('    if n < 2:')")
    selenium.run("shell.push('        return 1')")
    selenium.run("shell.push('    else:')")
    selenium.run("shell.push('        return n * factorial(n - 1)')")
    selenium.run("shell.push('')")
    selenium.run("shell.push('factorial(10)')")
    selenium.run_js("await pyodide.runPythonAsync('await shell.run_complete');")
    assert selenium.run("result") == 3628800

    # with package load
    selenium.run("shell.push('import pytz')")
    selenium.run("shell.push('pytz.utc.zone')")
    selenium.run_js("await pyodide.runPythonAsync('await shell.run_complete');")
    assert selenium.run("result") == "UTC"


def test_completion(selenium, safe_selenium_sys_redirections):
    selenium.run(
        """
        from pyodide import console

        shell = console._InteractiveConsole()
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
        from pyodide.console import _InteractiveConsole

        result = None

        def display(value):
            global result
            result = value

        shell = _InteractiveConsole()
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
[[;;;terminal-error]Traceback (most recent call last):]
[[;;;terminal-error]  File "<console>", line 1, in <module>]
[[;;;terminal-error]Exception: hi]`
        ]);

        term.clear();
        term.exec("from _pyodide_core import trigger_fatal_error; trigger_fatal_error()");
        await term.ready;
        result.push([term.get_output(),
`>>> from _pyodide_core import trigger_fatal_error; trigger_fatal_error()
[[;;;terminal-error]Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.]
[[;;;terminal-error]The cause of the fatal error was:]
[[;;;terminal-error]Error: intentionally triggered fatal error!]
[[;;;terminal-error]Look in the browser console for more details.]`
        ]);

        await sleep(30);
        assert(() => term.paused());
        return result;
        """
    )
    for [x, y] in result:
        assert x == y
