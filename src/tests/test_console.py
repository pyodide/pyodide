from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

from pyodide import console  # noqa: E402


def test_stream_redirection():
    my_buffer = ""

    def stdout_callback(string):
        nonlocal my_buffer
        my_buffer += string

    my_stream = console._StdStream(stdout_callback)

    print("foo", file=my_stream)
    assert my_buffer == "foo\n"
    print("bar", file=my_stream)
    assert my_buffer == "foo\nbar\n"


def test_interactive_console_streams():

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

    # redirections disabled at destruction
    shell.restore_stdstreams()

    my_stdout = ""
    my_stderr = ""

    print("bar")
    assert my_stdout == ""

    print("foo", file=sys.stdout)
    assert my_stderr == ""
