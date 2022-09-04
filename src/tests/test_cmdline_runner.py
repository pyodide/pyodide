import re
import sys

import pytest

import pyodide
from pyodide_build.common import emscripten_version, get_pyodide_root


@pytest.mark.xfail_browsers(chrome="node only", firefox="node only")
def test_cmdline_runner(selenium):
    pyodide_root = get_pyodide_root()
    import subprocess

    result = subprocess.run(
        [pyodide_root / "tools/python.js", "-V"], capture_output=True, encoding="utf8"
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + sys.version.partition(" ")[0]
    assert result.stderr == ""

    result = subprocess.run(
        [
            pyodide_root / "tools/python.js",
            "-c",
            "from pyodide import __version__; print(__version__)",
        ],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == pyodide.__version__
    assert result.stderr == ""

    result = subprocess.run(
        [pyodide_root / "tools/python.js", "-m", "platform"],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == f"Emscripten-{emscripten_version()}-wasm32-32bit"

    result = subprocess.run(
        [pyodide_root / "tools/python.js", "-c"], capture_output=True, encoding="utf8"
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert (
        re.sub("/[/a-z]*/tools/python.js", "<...>/tools/python.js", result.stderr)
        == """\
Argument expected for the -c option
usage: <...>/tools/python.js [option] ... [-c cmd | -m mod | file | -] [arg] ...
Try `python -h' for more information.
"""
    )
