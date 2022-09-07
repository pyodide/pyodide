import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent

import pytest

import pyodide
from pyodide_build.common import emscripten_version, get_pyodide_root

only_node = pytest.mark.xfail_browsers(chrome="node only", firefox="node only")

pyodide_root = get_pyodide_root()
script_path = pyodide_root / "tools/python"


@only_node
def test_python_version(selenium):
    result = subprocess.run([script_path, "-V"], capture_output=True, encoding="utf8")
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + sys.version.partition(" ")[0]
    assert result.stderr == ""


@only_node
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


@only_node
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


@only_node
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


@only_node
def test_dash_m(selenium):
    result = subprocess.run(
        [script_path, "-m", "platform"],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == f"Emscripten-{emscripten_version()}-wasm32-32bit"


@only_node
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


@contextmanager
def venv_ctxmgr(path):
    from pyodide_build.out_of_tree.venv import create_pyodide_venv

    create_pyodide_venv(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def venv():
    path = Path(".venv-pyodide-tmp-test")
    with venv_ctxmgr(path) as venv:
        yield venv


@only_node
def test_venv_success_log(selenium, capsys):
    with venv_ctxmgr(Path(".venv-pyodide-tmp-test")):
        msg = dedent(
            """
            Creating Pyodide virtualenv at .venv-pyodide-tmp-test
            ... Configuring virtualenv
            ... Installing standard library
            Successfully created Pyodide virtual environment!
        """
        ).strip()
    captured = capsys.readouterr()
    assert captured.out.strip() == msg
    assert captured.err == ""


@only_node
def test_venv_fail_log(selenium, capsys):
    path = Path(".venv-pyodide-tmp-test")
    try:
        path.mkdir()
        with pytest.raises(SystemExit, match="1"):
            with venv_ctxmgr(path):
                pass
    finally:
        shutil.rmtree(path, ignore_errors=True)
    msg = dedent("Creating Pyodide virtualenv at .venv-pyodide-tmp-test")
    captured = capsys.readouterr()
    assert captured.out.strip() == msg
    assert (
        captured.err
        == "ERROR: dest directory '.venv-pyodide-tmp-test' already exists\n"
    )


@only_node
def test_venv_version(selenium, venv):
    result = subprocess.run(
        [venv / "bin/python", "--version"], capture_output=True, encoding="utf8"
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + sys.version.partition(" ")[0]
    assert result.stderr == ""


@only_node
def test_venv_pyodide_version(selenium, venv):
    result = subprocess.run(
        [
            venv / "bin/python",
            "-c",
            "from pyodide import __version__; print(__version__)",
        ],
        capture_output=True,
        encoding="utf8",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == pyodide.__version__
    assert result.stderr == ""


def install_pkg(venv, pkgname):
    return subprocess.run(
        [
            venv / "bin/pip",
            "install",
            pkgname,
        ],
        capture_output=True,
        encoding="utf8",
    )


def test_venv_pip_install_1(selenium, venv):
    """pure Python package with no dependencies from pypi"""
    result = install_pkg(venv, "more-itertools")
    assert result.returncode == 0
    cleaned_stdout = result.stdout.strip()
    # delete lines indicating whether package was downloaded or used from cache
    # since these don't reproduce.
    cleaned_stdout = re.sub("^  .*?\n", "", cleaned_stdout, flags=re.MULTILINE)
    assert (
        cleaned_stdout
        == dedent(
            """
            Looking in links: /src/dist
            Collecting more-itertools
            Installing collected packages: more-itertools
            Successfully installed more-itertools-8.14.0
            """
        ).strip()
    )

    result = subprocess.run(
        [
            venv / "bin/python",
            "-c",
            dedent(
                """
                from more_itertools import chunked
                iterable = range(9)
                print(list(chunked(iterable, 3)))
                """
            ),
        ],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stdout == str([[0, 1, 2], [3, 4, 5], [6, 7, 8]]) + "\n"


def test_venv_pip_install_2(selenium, venv):
    """pure Python package with dependencies from pypi"""
    result = install_pkg(venv, "requests")
    assert result.returncode == 0
    cleaned_stdout = result.stdout.strip()
    # delete lines indicating whether package was downloaded or used from cache
    # since these don't reproduce.
    cleaned_stdout = re.sub("^  .*?\n", "", cleaned_stdout, flags=re.MULTILINE)
    cleaned_stdout = "\n".join(sorted(cleaned_stdout.split("\n")))
    assert (
        cleaned_stdout
        == dedent(
            """
            Collecting certifi>=2017.4.17
            Collecting charset-normalizer<3,>=2
            Collecting idna<4,>=2.5
            Collecting requests
            Collecting urllib3<1.27,>=1.21.1
            Installing collected packages: urllib3, idna, charset-normalizer, certifi, requests
            Looking in links: /src/dist
            Successfully installed certifi-2022.6.15 charset-normalizer-2.1.1 idna-3.3 requests-2.28.1 urllib3-1.26.12
            """
        ).strip()
    )


def test_venv_pip_install_3(selenium, venv):
    """impure python package from pypi"""
    result = install_pkg(venv, "psutil")
    assert result.returncode != 0
    assert result.stdout == "Looking in links: /src/dist\n"
    assert (
        result.stderr.strip()
        == dedent(
            """
            ERROR: Could not find a version that satisfies the requirement psutil (from versions: none)
            ERROR: No matching distribution found for psutil
            """
        ).strip()
    )


def test_venv_pip_install_4(selenium, venv):
    """pure python package from pypi that depends on impure package"""
    result = install_pkg(venv, "psutil-extra")
    assert result.returncode != 0


def test_venv_pip_install_regex(selenium, venv):
    """impure Python package built with Pyodide"""
    result = install_pkg(venv, "regex")
    assert result.returncode == 0
    cleaned_stdout = result.stdout.strip()
    # delete lines indicating whether package was downloaded or used from cache
    # since these don't reproduce.
    cleaned_stdout = re.sub("^  .*?\n", "", cleaned_stdout, flags=re.MULTILINE)
    assert (
        cleaned_stdout
        == dedent(
            """
            Looking in links: /src/dist
            Processing ./dist/regex-2022.6.2-cp310-cp310-emscripten_3_1_20_wasm32.whl
            Installing collected packages: regex
            Successfully installed regex-2022.6.2
            """
        ).strip()
    )

    result = subprocess.run(
        [
            venv / "bin/python",
            "-c",
            dedent(
                r"""
                import regex
                m = regex.match(r"(?:(?P<word>\w+) (?P<digits>\d+)\n)+", "one 1\ntwo 2\nthree 3\n")
                print(m.capturesdict())
                """
            ),
        ],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert (
        result.stdout
        == "{'word': ['one', 'two', 'three'], 'digits': ['1', '2', '3']}" + "\n"
    )
