import re
import subprocess
import sys

import pytest

import pyodide
from pyodide_build.common import emscripten_version, get_pyodide_root

mark = pytest.mark.xfail_browsers(
    chrome="node only", firefox="node only", safari="node only"
)

pyodide_root = get_pyodide_root()
script_path = pyodide_root / "tools/python"


@mark
def test_python_version(selenium):
    result = subprocess.run([script_path, "-V"], capture_output=True, encoding="utf8")
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + sys.version.partition(" ")[0]
    assert result.stderr == ""


@mark
def test_dash_c(selenium):
    result = subprocess.run(
        [
            script_path,
            "-c",
            "from pyodide import __version__; print(__version__)",
        ],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == pyodide.__version__
    assert result.stderr == ""


@mark
def test_ensure_future(selenium):
    result = subprocess.run(
        [
            script_path,
            "-c",
            """\
import asyncio
async def test():
    await asyncio.sleep(0.5)
    print("done")
asyncio.ensure_future(test())
""",
        ],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == "done"


@mark
def test_flush_on_exit(selenium):
    result = subprocess.run(
        [
            script_path,
            "-c",
            """\
print("a", end="")
print("b", end="")
print("c", end="")
""",
        ],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == "abc"


@mark
def test_dash_m(selenium):
    result = subprocess.run(
        [script_path, "-m", "platform"],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == f"Emscripten-{emscripten_version()}-wasm32-32bit"


@mark
def test_invalid_cmdline_option(selenium):
    result = subprocess.run([script_path, "-c"], capture_output=True, encoding="utf8")
    assert result.returncode != 0
    assert result.stdout == ""
    assert (
        re.sub("/[/a-z]*/tools/python", "<...>/tools/python", result.stderr)
        == """\
Argument expected for the -c option
usage: <...>/tools/python [option] ... [-c cmd | -m mod | file | -] [arg] ...
Try `python -h' for more information.
"""
    )
