import pytest
from pathlib import Path
import sys
from selenium.webdriver.support.ui import WebDriverWait

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


@pytest.fixture
def safe_selenium_sys_redirections(selenium):
    selenium.run("_redirected = sys.stdout, sys.stderr, sys.displayhook")
    yield
    selenium.run("sys.stdout, sys.stderr, sys.displayhook = _redirected")


def test_interactive_console(selenium, safe_selenium_sys_redirections):
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
    WebDriverWait(selenium, 1).until(lambda driver: selenium.run("result == 5"))

    selenium.run("shell.push('x ** 2')")
    WebDriverWait(selenium, 1).until(lambda driver: selenium.run("result == 25"))

    # import numpy
    selenium.run("shell.push('import numpy as np; np.gcd(6, 15)')")
    WebDriverWait(selenium, 10).until(lambda driver: selenium.run("result == 3"))
    selenium.run("shell.push('int(np.pi * 100)')")
    WebDriverWait(selenium, 1).until(lambda driver: selenium.run("result == 314"))
