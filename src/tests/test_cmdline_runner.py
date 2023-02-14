import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any

import pytest

import pyodide
from pyodide_build.common import emscripten_version, get_pyodide_root
from pyodide_build.install_xbuildenv import download_xbuildenv, install_xbuildenv

only_node = pytest.mark.xfail_browsers(
    chrome="node only", firefox="node only", safari="node only"
)


def check_emscripten():
    if not shutil.which("emcc"):
        pytest.skip("Needs Emscripten")


def needs_emscripten(x):
    if not shutil.which("emcc"):
        return pytest.mark.skip("Needs Emscripten")(x)
    return x


pyodide_root = get_pyodide_root()
script_path = pyodide_root / "dist/python"


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
        re.sub("/[/a-z]*/dist/python", "<...>/python", result.stderr)
        == """\
Argument expected for the -c option
usage: <...>/python [option] ... [-c cmd | -m mod | file | -] [arg] ...
Try `python -h' for more information.
"""
    )


@contextmanager
def venv_ctxmgr(path):
    check_emscripten()

    if TYPE_CHECKING:
        create_pyodide_venv: Any = None
    else:
        from pyodide_build.out_of_tree.venv import create_pyodide_venv

    create_pyodide_venv(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def venv(runtime):
    if runtime != "node":
        pytest.xfail("node only")
    check_emscripten()
    path = Path(".venv-pyodide-tmp-test")
    with venv_ctxmgr(path) as venv:
        yield venv


@only_node
@needs_emscripten
def test_venv_success_log(selenium, capsys):
    with venv_ctxmgr(Path(".venv-pyodide-tmp-test")):
        msgs = [
            "Creating Pyodide virtualenv at .venv-pyodide-tmp-test",
            "... Configuring virtualenv",
            "... Installing standard library",
            "Successfully created Pyodide virtual environment!",
        ]
    captured = capsys.readouterr()
    assert [l.strip() for l in captured.out.splitlines()] == msgs
    assert captured.err == ""


@only_node
@needs_emscripten
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
        "ERROR: dest directory '.venv-pyodide-tmp-test' already exists" in captured.err
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
            "--disable-pip-version-check",
        ],
        capture_output=True,
        encoding="utf8",
    )


def clean_pkg_install_stdout(stdout: str) -> str:
    # delete lines indicating whether package was downloaded or used from cache
    # since these don't reproduce.
    stdout = re.sub(r"^  .*?\n", "", stdout, flags=re.MULTILINE)
    stdout = re.sub(r"^\[notice\].*?\n", "", stdout, flags=re.MULTILINE)
    # Remove version numbers
    stdout = re.sub(r"(?<=[<>=_-])[\d+](\.?_?[\d+])*", "*", stdout)
    stdout = re.sub(r" /[a-zA-Z0-9/]*/dist", " .../dist", stdout)
    stdout = re.sub(r"cp[0-9]*", "cpxxx", stdout)

    return stdout.strip()


def test_clean_pkg_install_stdout():
    assert (
        clean_pkg_install_stdout(
            """\
Looking in links: /src/dist
Processing ./dist/regex-2.0-cp310-cp310-emscripten_3_1_20_wasm32.whl
Installing collected packages: regex
Successfully installed regex-2.0

[notice] A new release of pip available: 22.1.2 -> 22.2.2
[notice] To update, run: /root/repo/.venv-pyodide-tmp-test/bin/python3.10-host -m pip install --upgrade pip
"""
        )
        == """\
Looking in links: .../dist
Processing ./dist/regex-*-cpxxx-cpxxx-emscripten_*_wasm32.whl
Installing collected packages: regex
Successfully installed regex-*\
"""
    )


@only_node
def test_pip_install_from_pypi_nodeps(selenium, venv):
    """pure Python package with no dependencies from pypi"""
    result = install_pkg(venv, "more-itertools")
    assert result.returncode == 0
    assert (
        clean_pkg_install_stdout(result.stdout)
        == dedent(
            """
            Looking in links: .../dist
            Collecting more-itertools
            Installing collected packages: more-itertools
            Successfully installed more-itertools-*
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


@only_node
def test_pip_install_from_pypi_deps(selenium, venv):
    """pure Python package with dependencies from pypi"""
    result = install_pkg(venv, "requests==2.28.1")
    assert result.returncode == 0
    cleaned_stdout = clean_pkg_install_stdout(result.stdout)
    # Sort packages since they don't come in a consistent order
    cleaned_stdout = "\n".join(sorted(cleaned_stdout.split("\n")))
    assert (
        cleaned_stdout
        == dedent(
            """
            Collecting certifi>=*
            Collecting charset-normalizer<*,>=*
            Collecting idna<*,>=*
            Collecting requests==*
            Collecting urllib3<*,>=*
            Installing collected packages: urllib3, idna, charset-normalizer, certifi, requests
            Looking in links: .../dist
            Successfully installed certifi-* charset-normalizer-* idna-* requests-* urllib3-*
            """
        ).strip()
    )


@only_node
def test_pip_install_impure(selenium, venv):
    """impure python package from pypi"""
    result = install_pkg(venv, "psutil")
    assert result.returncode != 0
    assert clean_pkg_install_stdout(result.stdout) == "Looking in links: .../dist"
    assert (
        result.stderr.strip()
        == dedent(
            """
            ERROR: Could not find a version that satisfies the requirement psutil (from versions: none)
            ERROR: No matching distribution found for psutil
            """
        ).strip()
    )


@only_node
def test_pip_install_deps_impure(selenium, venv):
    """pure python package from pypi that depends on impure package"""
    result = install_pkg(venv, "psutil-extra")
    assert result.returncode != 0


@only_node
def test_pip_install_from_pyodide(selenium, venv):
    """impure Python package built with Pyodide"""
    result = install_pkg(venv, "regex")
    assert result.returncode == 0
    assert (
        clean_pkg_install_stdout(result.stdout)
        == dedent(
            """
            Looking in links: .../dist
            Processing ./dist/regex-*-cpxxx-cpxxx-emscripten_*_wasm32.whl
            Installing collected packages: regex
            Successfully installed regex-*
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


def test_pypa_index(tmp_path):
    """Test that installing packages from the python package index works as
    expected."""
    path = Path(tmp_path)
    version = "0.21.0"  # just need some version that already exists
    download_xbuildenv(version, path)

    # We don't need host dependencies for this test so zero them out
    (path / "xbuildenv/requirements.txt").write_text("")

    install_xbuildenv(version, path)
    pip_opts = [
        "--index-url",
        "file:" + str((path / "xbuildenv/pyodide-root/pypa_index").resolve()),
        "--platform=emscripten_3_1_14_wasm32",
        "--only-binary=:all:",
        "--python-version=310",
        "-t",
        str(path / "temp_lib"),
    ]
    to_install = [
        "numpy",
        "sharedlib-test-py",
        "micropip",
        "attrs",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            *pip_opts,
            *to_install,
        ],
        capture_output=True,
        encoding="utf8",
    )
    print("\n\nstdout:")
    print(result.stdout)
    print("\n\nstderr:")
    print(result.stderr)
    assert result.returncode == 0
    stdout = re.sub(r"(?<=[<>=-])([\d+]\.?)+", "*", result.stdout)
    assert (
        stdout.strip().rsplit("\n", 1)[-1]
        == "Successfully installed attrs-* micropip-* numpy-* sharedlib-test-py-*"
    )


def test_sys_exit(selenium, venv):
    result = subprocess.run(
        [venv / "bin/python", "-c", "import sys; sys.exit(0)"],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    result = subprocess.run(
        [venv / "bin/python", "-c", "import sys; sys.exit(12)"],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 12
    assert result.stdout == ""
    assert result.stderr == ""
