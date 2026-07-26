"""Tests for the Windows launchers, python.exe and python.bat.

python.exe re-invokes the python.bat next to it, which either redirects to
pip.bat or hands off to node. The first two classes swap in stubs so a failure
points at the argument handling rather than at the build, and the last runs the
whole chain against a real dist.

They read the launchers out of dist/, so run `make dist/python.exe` or unpack a
build there first:

    pytest tools/test_windows_launchers.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="the launchers are Windows-only"
)

# Reports one argument per line with the quotes stripped, so a test can compare
# against the list it passed. Stops at the first empty argument, which is why no
# case below uses one.
ECHO_ARGS_BAT = """\
@echo off
:loop
if "%~1"=="" goto :end
echo [%~1]
shift
goto loop
:end
"""

# Stands in for node. The version check runs first and its output becomes a node
# flag, so that invocation stays quiet.
NODE_STUB_BAT = """\
@echo off
echo %1 | findstr /c:"__pyodide_node_check" >nul
if not errorlevel 1 exit /b 0
:loop
if "%~1"=="" goto :end
echo [%~1]
shift
goto loop
:end
"""


DIST = Path(__file__).parents[1] / "dist"


@pytest.fixture
def dist() -> Path:
    if not (DIST / "python.exe").exists() or not (DIST / "python.bat").exists():
        pytest.skip(f"No launchers in {DIST}")
    return DIST


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """A directory with a space in its name, which is what broke python.exe."""
    path = tmp_path / "dir with space"
    path.mkdir()
    return path


@pytest.fixture
def node_stub(tmp_path: Path) -> dict[str, str]:
    """An environment whose PATH finds our stub node before any real one."""
    stub_dir = tmp_path / "stub bin"
    stub_dir.mkdir()
    (stub_dir / "node.bat").write_text(NODE_STUB_BAT)
    path = os.environ.get("PATH", "")
    return os.environ | {"PATH": f"{stub_dir}{os.pathsep}{path}"}


def run(
    launcher: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(launcher), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def reported(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestPythonExe:
    """python.exe hands its arguments to the python.bat beside it."""

    @pytest.fixture
    def launcher(self, dist: Path, work_dir: Path) -> Path:
        shutil.copy(dist / "python.exe", work_dir / "python.exe")
        (work_dir / "python.bat").write_text(ECHO_ARGS_BAT)
        return work_dir / "python.exe"

    @pytest.mark.parametrize(
        "args",
        [
            ["-V"],
            ["-c", "import sys"],
            # A quoted argument used to make cmd strip the quotes from the path
            # to python.bat, splitting it at the space
            ["-m", "pytest", "-k", "not mypy"],
            ["-c", "print('hello world')"],
            ["-c", 'print("double quoted")'],
            ["--this-program=C:\\Program Files\\pyodide\\python.exe"],
            ["a b", "c\td"],
            ["back\\slash", "trailing\\"],
            # cmd reads the line on the way through, so anything it treats as
            # syntax has to stay quoted
            ["-c", "print(1 & 2)"],
            ["a&b"],
            ["a|b"],
            ["a>b", "c<d"],
            ["(parens)"],
            ["caret^"],
            ["-c", "print('hi!')"],
            # A lone % is literal. A %VAR% pair is not: cmd expands it on the
            # way through, as it did before this was routed through cmd.exe
            # explicitly, so there is nothing here that asserts otherwise.
            ["50%"],
            ["-m", "http.server", "--bind", "::1", "8000"],
        ],
        ids=" ".join,
    )
    def test_arguments_are_forwarded(self, launcher: Path, args: list[str]) -> None:
        result = run(launcher, *args)

        assert result.returncode == 0, result.stderr
        assert reported(result) == [f"[{arg}]" for arg in args]

    def test_exit_code_is_propagated(self, launcher: Path) -> None:
        (launcher.parent / "python.bat").write_text("@echo off\nexit /b 42\n")

        assert run(launcher).returncode == 42

    def test_missing_python_bat_fails(self, launcher: Path) -> None:
        (launcher.parent / "python.bat").unlink()

        assert run(launcher, "-V").returncode != 0


class TestPythonBat:
    """python.bat either redirects to pip.bat or hands off to node."""

    @pytest.fixture
    def launcher(self, dist: Path, work_dir: Path) -> Path:
        shutil.copy(dist / "python.bat", work_dir / "python.bat")
        return work_dir / "python.bat"

    def test_pip_receives_the_arguments_after_m_pip(self, launcher: Path) -> None:
        (launcher.parent / "pip.bat").write_text(ECHO_ARGS_BAT)

        result = run(launcher, "-m", "pip", "install", "six")

        assert result.returncode == 0, result.stderr
        # "-m pip" is consumed here, so pip must not see it
        assert reported(result) == ["[install]", "[six]"]

    def test_pip_arguments_keep_their_spaces(self, launcher: Path) -> None:
        (launcher.parent / "pip.bat").write_text(ECHO_ARGS_BAT)

        result = run(launcher, "-m", "pip", "install", "-r", "a file.txt")

        assert result.returncode == 0, result.stderr
        assert reported(result) == ["[install]", "[-r]", "[a file.txt]"]

    def test_pip_arguments_keep_their_exclamation_marks(self, launcher: Path) -> None:
        (launcher.parent / "pip.bat").write_text(ECHO_ARGS_BAT)

        result = run(launcher, "-m", "pip", "install", "a!b!c")

        assert result.returncode == 0, result.stderr
        assert reported(result) == ["[install]", "[a!b!c]"]

    def test_bare_m_pip_is_accepted(self, launcher: Path) -> None:
        (launcher.parent / "pip.bat").write_text(ECHO_ARGS_BAT)

        result = run(launcher, "-m", "pip")

        assert result.returncode == 0, result.stderr
        assert reported(result) == []

    def test_pip_exit_code_is_propagated(self, launcher: Path) -> None:
        (launcher.parent / "pip.bat").write_text("@echo off\nexit /b 3\n")

        assert run(launcher, "-m", "pip", "install", "six").returncode == 3

    def test_missing_pip_is_reported(self, launcher: Path) -> None:
        result = run(launcher, "-m", "pip", "install", "six")

        assert result.returncode == 1
        assert "Cannot find pyodide pip" in result.stderr

    def test_m_without_pip_is_not_redirected(
        self, launcher: Path, node_stub: dict[str, str]
    ) -> None:
        (launcher.parent / "pip.bat").write_text(ECHO_ARGS_BAT)

        result = run(launcher, "-m", "pytest", env=node_stub)

        assert result.returncode == 0, result.stderr
        assert "python_cli_entry.mjs" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ["-V"],
            ["-c", "import sys"],
            ["-m", "pytest", "-k", "not mypy"],
            ["-c", "print('hello world')"],
            # Delayed expansion used to swallow the "!"
            ["-c", "print('hi!')"],
            ["-c", "print('a!b!c')"],
            ["script.py", "an argument"],
            ["back\\slash"],
        ],
        ids=" ".join,
    )
    def test_arguments_reach_node(
        self, launcher: Path, node_stub: dict[str, str], args: list[str]
    ) -> None:
        result = run(launcher, *args, env=node_stub)

        assert result.returncode == 0, result.stderr
        # The entry point and --this-program come first, ours follow
        assert reported(result)[-len(args) :] == [f"[{arg}]" for arg in args]

    def test_this_program_points_at_the_exe(
        self, launcher: Path, node_stub: dict[str, str]
    ) -> None:
        result = run(launcher, "-V", env=node_stub)

        assert result.returncode == 0, result.stderr
        expected = str(launcher.with_suffix(".exe"))
        assert f"[--this-program={expected}]" in reported(result)

    def test_missing_node_is_reported(self, launcher: Path, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()

        result = run(launcher, "-V", env=os.environ | {"PATH": str(empty)})

        assert result.returncode == 1
        assert "No node executable found" in result.stderr

    def test_the_version_check_file_is_cleaned_up(
        self, launcher: Path, node_stub: dict[str, str], tmp_path: Path
    ) -> None:
        # A temp directory of our own, so nothing else on the machine can leave
        # a matching file behind and make this flaky
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        run(launcher, "-V", env=node_stub | {"TEMP": str(temp_dir)})

        assert list(temp_dir.glob("__pyodide_node_check_*.js")) == []


class TestRealBuild:
    """The whole chain: python.exe, python.bat, node and Pyodide itself."""

    @pytest.fixture
    def launcher(self, dist: Path, work_dir: Path) -> Path:
        shutil.copytree(dist, work_dir, dirs_exist_ok=True)
        return work_dir / "python.exe"

    def test_it_runs_python(self, launcher: Path) -> None:
        result = run(launcher, "-c", "print(6 * 7)")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "42"

    def test_it_is_emscripten(self, launcher: Path) -> None:
        result = run(launcher, "-c", "import sys; print(sys.platform)")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "emscripten"

    def test_sys_executable_is_the_exe(self, launcher: Path) -> None:
        result = run(launcher, "-c", "import sys; print(sys.executable)")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(launcher)

    @pytest.mark.parametrize(
        "code, expected",
        [
            ("print('exclamation!')", "exclamation!"),
            ("print('a!b!c')", "a!b!c"),
            ("print(1 & 2)", "0"),
            ("print('one two')", "one two"),
            ('print("percent 50%")', "percent 50%"),
            ("print('pipe | caret ^')", "pipe | caret ^"),
        ],
    )
    def test_awkward_arguments_survive(
        self, launcher: Path, code: str, expected: str
    ) -> None:
        result = run(launcher, "-c", code)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected

    def test_pip_without_a_venv_is_reported(self, launcher: Path) -> None:
        # A bare dist has no pip.bat, that only appears in a Pyodide venv
        result = run(launcher, "-m", "pip", "install", "six")

        assert result.returncode == 1
        assert "Cannot find pyodide pip" in result.stderr
