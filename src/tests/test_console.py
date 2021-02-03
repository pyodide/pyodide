import pytest
from pathlib import Path
import sys
import io

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

from pyodide import console  # noqa: E402


def test_stream_redirection():
    my_buffer = ""

    def callback(string):
        nonlocal my_buffer
        my_buffer += string

    my_stream = console._StdStream(callback)

    print("foo", file=my_stream)
    assert my_buffer == "foo\n"
    print("bar", file=my_stream)
    assert my_buffer == "foo\nbar\n"


@pytest.fixture
def safe_sys_redirections():
    redirected = sys.stdout, sys.stderr, sys.displayhook
    yield
    sys.stdout, sys.stderr, sys.displayhook = redirected


def test_interactive_console_streams(safe_sys_redirections):

    my_stdout = ""
    my_stderr = ""

    def stdout_callback(string):
        nonlocal my_stdout
        my_stdout += string

    def stderr_callback(string):
        nonlocal my_stderr
        my_stderr += string

    ##########################
    # Persistent redirection #
    ##########################
    shell = console.InteractiveConsole(
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        persistent_stream_redirection=True,
    )

    # std names
    assert sys.stdout.name == "<stdout>"
    assert sys.stderr.name == "<stderr>"

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

    shell.restore_stdstreams()

    my_stdout = ""
    my_stderr = ""

    print("bar")
    assert my_stdout == ""

    print("foo", file=sys.stdout)
    assert my_stderr == ""

    ##############################
    # Non persistent redirection #
    ##############################
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

    shell.push("1+1")
    assert my_stdout == "foobar\nfoobar\n2\n"


def test_repr(safe_sys_redirections):
    sep = "..."
    for string in ("x" * 10 ** 5, "x" * (10 ** 5 + 1)):
        for limit in (9, 10, 100, 101):
            assert len(
                console.repr_shorten(string, limit=limit, separator=sep)
            ) == 2 * (limit // 2) + len(sep)

    sys.stdout = io.StringIO()
    console.displayhook(
        [0] * 100, lambda v: console.repr_shorten(v, 100, separator=sep)
    )
    assert len(sys.stdout.getvalue()) == 100 + len(sep) + 1  # for \n


@pytest.fixture
def safe_selenium_sys_redirections(selenium):
    selenium.run("_redirected = sys.stdout, sys.stderr, sys.displayhook")
    yield
    selenium.run("sys.stdout, sys.stderr, sys.displayhook = _redirected")


def test_interactive_console(selenium, safe_selenium_sys_redirections):
    def ensure_run_completed():
        selenium.driver.execute_async_script(
            """
        const done = arguments[arguments.length - 1];
        pyodide.globals.shell.run_complete.then(done);
        """
        )

    selenium.run(
        """
    from pyodide.console import InteractiveConsole

    result = None

    def displayhook(value):
        global result
        result = value

    shell = InteractiveConsole()
    sys.displayhook = displayhook"""
    )

    selenium.run("shell.push('x = 5')")
    selenium.run("shell.push('x')")
    ensure_run_completed()
    assert selenium.run("result") == 5

    selenium.run("shell.push('x ** 2')")
    ensure_run_completed()
    assert selenium.run("result") == 25

    selenium.run("shell.push('def f(x):')")
    selenium.run("shell.push('    return x*x + 1')")
    selenium.run("shell.push('')")
    selenium.run("shell.push('[f(x) for x in range(5)]')")
    ensure_run_completed()
    assert selenium.run("result") == [1, 2, 5, 10, 17]

    selenium.run("shell.push('def factorial(n):')")
    selenium.run("shell.push('    if n < 2:')")
    selenium.run("shell.push('        return 1')")
    selenium.run("shell.push('    else:')")
    selenium.run("shell.push('        return n * factorial(n - 1)')")
    selenium.run("shell.push('')")
    selenium.run("shell.push('factorial(10)')")
    ensure_run_completed()
    assert selenium.run("result") == 3628800

    # with package load
    selenium.run("shell.push('import pytz')")
    selenium.run("shell.push('pytz.utc.zone')")
    ensure_run_completed()
    assert selenium.run("result") == "UTC"


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
