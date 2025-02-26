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
from pyodide_build.build_env import (
    emscripten_version,
    get_build_environment_vars,
    get_pyodide_root,
)
from pyodide_build.xbuildenv import CrossBuildEnvManager

PYVERSION = get_build_environment_vars(get_pyodide_root())["PYVERSION"]

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
    result = subprocess.run(
        [script_path, "-V"], capture_output=True, encoding="utf8", check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + PYVERSION
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
        check=False,
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
        check=False,
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
        check=False,
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
        check=False,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == f"Emscripten-{emscripten_version()}-wasm32-32bit"


@only_node
def test_dash_m_pip(selenium, monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("PATH", str(tmp_path), prepend=":")
    pip_path = tmp_path / "pip"
    pip_path.write_text("echo 'pip got' $@")
    os.chmod(pip_path, 0o777)

    result = subprocess.run(
        [script_path, "-m", "pip", "install", "pytest"],
        capture_output=True,
        encoding="utf8",
        check=False,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == "pip got install pytest"


@only_node
def test_invalid_cmdline_option(selenium):
    result = subprocess.run(
        [script_path, "-c"], capture_output=True, encoding="utf8", check=False
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert (
        re.sub("/.*/dist/python", "<...>/python", result.stderr)
        == """\
Argument expected for the -c option
usage: <...>/python [option] ... [-c cmd | -m mod | file | -] [arg] ...
Try `python -h' for more information.
"""
    )


@only_node
def test_extra_mounts(selenium, tmp_path, monkeypatch):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    tmp_path_a = dir_a / "script.py"
    tmp_path_b = dir_b / "script.py"
    tmp_path_a.write_text("print('hello 1')")
    tmp_path_b.write_text("print('hello 2')")
    monkeypatch.setenv("_PYODIDE_EXTRA_MOUNTS", f"{dir_a}:{dir_b}")
    result = subprocess.run(
        [script_path, tmp_path_a], capture_output=True, encoding="utf8", check=False
    )
    assert result.returncode == 0
    assert result.stdout == "hello 1\n"
    assert result.stderr == ""
    result = subprocess.run(
        [script_path, tmp_path_b], capture_output=True, encoding="utf8", check=False
    )
    assert result.returncode == 0
    assert result.stdout == "hello 2\n"
    assert result.stderr == ""


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
        [venv / "bin/python", "--version"],
        capture_output=True,
        encoding="utf8",
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "Python " + PYVERSION
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
        check=False,
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
        check=False,
    )


def check_installed_packages(venv, pkgs):
    python = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = venv / "lib" / python / "site-packages"
    not_found = [
        pkg
        for pkg in pkgs
        if not next(site_packages.glob(pkg + "*" + ".dist-info"), None)
    ]
    assert not_found == []


def clean_pkg_install_stdout(stdout: str) -> str:
    # delete lines indicating whether package was downloaded or used from cache
    # since these don't reproduce.
    stdout = re.sub(r"^  .*?\n", "", stdout, flags=re.MULTILINE)
    stdout = re.sub(r"^\[notice\].*?\n", "", stdout, flags=re.MULTILINE)
    stdout = re.sub(r"^.*cached.*?\n", "", stdout, flags=re.MULTILINE)
    stdout = re.sub(r"^.*Downloading.*?\n", "", stdout, flags=re.MULTILINE)
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
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == str([[0, 1, 2], [3, 4, 5], [6, 7, 8]]) + "\n"


@only_node
def test_pip_install_from_pypi_deps(selenium, venv):
    """pure Python package with dependencies from pypi"""
    result = install_pkg(venv, "requests==2.28.1")
    assert result.returncode == 0
    check_installed_packages(
        venv, ["certifi", "charset_normalizer", "idna", "requests", "urllib3"]
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
def test_pip_install_executable(selenium, venv):
    """impure python package from pypi"""
    result = install_pkg(venv, "pytest")
    assert result.returncode == 0
    python = f"python{sys.version_info.major}.{sys.version_info.minor}"
    pytest_script = (venv / "bin/pytest").read_text()
    shebang = pytest_script.splitlines()[0]
    assert shebang == "#!" + str((venv / "bin" / python).absolute())


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
            Processing ./dist/regex-*-cpxxx-cpxxx-pyodide_*_wasm32.whl
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
        check=False,
    )
    assert result.returncode == 0
    assert (
        result.stdout
        == "{'word': ['one', 'two', 'three'], 'digits': ['1', '2', '3']}" + "\n"
    )


def test_package_index(tmp_path):
    """Test that installing packages from the python package index works as
    expected."""
    path = Path(tmp_path)
    version = "0.26.0"  # just need some version that already exists + contains pyodide-lock.json

    mgr = CrossBuildEnvManager(path)
    mgr.install(version, skip_install_cross_build_packages=True, force_install=True)

    env_path = mgr.symlink_dir.resolve()

    pip_opts = [
        "--index-url",
        "file:" + str((env_path / "xbuildenv/pyodide-root/package_index").resolve()),
        "--platform=pyodide_2024_0_wasm32",
        "--only-binary=:all:",
        "--python-version=312",
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
        check=False,
    )

    assert result.returncode == 0
    stdout = re.sub(r"(?<=[<>=-])([\d+]\.?)+", "*", result.stdout)
    assert (
        stdout.strip().rsplit("\n", 1)[-1]
        == "Successfully installed attrs-* micropip-* numpy-* packaging-* sharedlib-test-py-*"
    )


def test_sys_exit(selenium, venv):
    result = subprocess.run(
        [venv / "bin/python", "-c", "import sys; sys.exit(0)"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    result = subprocess.run(
        [venv / "bin/python", "-c", "import sys; sys.exit(12)"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 12
    assert result.stdout == ""
    assert result.stderr == ""


def test_cpp_exceptions(selenium, venv):
    result = install_pkg(venv, "cpp-exceptions-test2")
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    result = subprocess.run(
        [venv / "bin/python", "-c", "import cpp_exceptions_test2"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 1
    assert "ImportError: oops" in result.stderr


@only_node
def test_pip_install_sys_platform_condition_kept(selenium, venv):
    """impure Python package built with Pyodide"""
    result = install_pkg(venv, "regex; sys_platform == 'emscripten'")
    assert result.returncode == 0
    assert (
        clean_pkg_install_stdout(result.stdout)
        == dedent(
            """
            Looking in links: .../dist
            Processing ./dist/regex-*-cpxxx-cpxxx-pyodide_*_wasm32.whl
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
        check=False,
    )
    assert result.returncode == 0
    assert (
        result.stdout
        == "{'word': ['one', 'two', 'three'], 'digits': ['1', '2', '3']}" + "\n"
    )


@only_node
def test_pip_install_sys_platform_condition_skipped(selenium, venv):
    """impure Python package built with Pyodide"""
    result = install_pkg(venv, "regex; sys_platform != 'emscripten'")
    assert result.returncode == 0
    ignoring = """Ignoring regex: markers 'sys_platform != "emscripten"' don't match your environment"""
    assert ignoring in result.stdout
