"""Tests for the Windows launchers, python.exe and python.bat.

python.exe re-invokes the python.bat beside it, which either redirects to
pip.bat or hands off to node. The first two classes swap those for reporters
that print their arguments back, the last runs Pyodide itself.

Needs a build in dist/:

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

REPO_ROOT = Path(__file__).parents[2]
DIST = REPO_ROOT / "dist"

REPORT_PY = """\
import sys

for arg in sys.argv[1:]:
    print(f"[{arg}]")
"""

REPORT_MJS = """\
for (const arg of process.argv.slice(2)) {
  console.log(`[${arg}]`);
}
"""


@pytest.fixture
def dist() -> Path:
    if not (DIST / "python.exe").exists() or not (DIST / "python.bat").exists():
        pytest.fail(f"No launchers in {DIST}, run `make dist/python.exe` first")
    return DIST


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """A directory with a space in its name, which is what broke python.exe."""
    path = tmp_path / "dir with space"
    path.mkdir()
    return path


def write_reporter_bat(path: Path) -> None:
    """Write a batch file that reports the arguments it was handed."""
    report = path.parent / "report_args.py"
    report.write_text(REPORT_PY)
    # absolute path, so nothing on PATH can shadow it
    path.write_text(f'@echo off\n"{sys.executable}" "{report}" %*\n')


def run(
    launcher: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a launcher, either python.exe or python.bat.

    CreateProcess runs a .bat through cmd.exe, and subprocess quotes by C
    runtime rules that cmd does not follow (bpo-34489), so keep arguments free
    of & | < > ^ in TestPythonBat. Those cases belong in TestPythonExe.
    """
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
        write_reporter_bat(work_dir / "python.bat")
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
            ["-c", "", "after an empty one"],
            # cmd reads the line on the way through
            ["-c", "print(1 & 2)"],
            ["a&b"],
            ["a|b"],
            ["a>b", "c<d"],
            ["(parens)"],
            ["caret^"],
            ["-c", "print('hi!')"],
            # a lone % is literal, a %VAR% pair is not: cmd expands it
            ["50%"],
            ["-c", "print('percent 50%')"],
            ["-c", 'print("percent 50%")'],
            ["-m", "http.server", "--bind", "::1", "8000"],
            ['-c', 'print("a & b")'],
            ['a"&b'],
            ['%PATH%'],
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
        # stands in for the entry point, so the real node splits the arguments
        (work_dir / "python_cli_entry.mjs").write_text(REPORT_MJS)
        return work_dir / "python.bat"

    def test_pip_receives_the_arguments_after_m_pip(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

        result = run(launcher, "-m", "pip", "install", "six")

        assert result.returncode == 0, result.stderr
        # "-m pip" is consumed here, so pip must not see it
        assert reported(result) == ["[install]", "[six]"]

    def test_pip_arguments_keep_their_spaces(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

        result = run(launcher, "-m", "pip", "install", "-r", "a file.txt")

        assert result.returncode == 0, result.stderr
        assert reported(result) == ["[install]", "[-r]", "[a file.txt]"]

    def test_pip_arguments_keep_their_exclamation_marks(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

        result = run(launcher, "-m", "pip", "install", "a!b!c")

        assert result.returncode == 0, result.stderr
        assert reported(result) == ["[install]", "[a!b!c]"]

    def test_an_empty_pip_argument_does_not_end_the_list(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

        result = run(launcher, "-m", "pip", "install", "", "six")

        assert result.returncode == 0, result.stderr
        assert reported(result) == ["[install]", "[]", "[six]"]

    def test_bare_m_pip_is_accepted(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

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

    def test_m_without_pip_is_not_redirected(self, launcher: Path) -> None:
        write_reporter_bat(launcher.parent / "pip.bat")

        result = run(launcher, "-m", "pytest")

        assert result.returncode == 0, result.stderr
        assert reported(result)[-2:] == ["[-m]", "[pytest]"]

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
            ["-c", "print('percent 50%')"],
            ["script.py", "an argument"],
            ["back\\slash"],
        ],
        ids=" ".join,
    )
    def test_arguments_reach_node(self, launcher: Path, args: list[str]) -> None:
        result = run(launcher, *args)

        assert result.returncode == 0, result.stderr
        assert reported(result)[-len(args) :] == [f"[{arg}]" for arg in args]

    def test_this_program_points_at_the_exe(self, launcher: Path) -> None:
        result = run(launcher, "-V")

        assert result.returncode == 0, result.stderr
        expected = str(launcher.with_suffix(".exe"))
        assert f"[--this-program={expected}]" in reported(result)

    def test_missing_node_is_reported(self, launcher: Path) -> None:
        # System32 stays on PATH, so where and findstr still work and node is
        # the only thing missing
        system32 = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32"

        result = run(launcher, "-V", env=os.environ | {"PATH": str(system32)})

        assert result.returncode == 1
        assert "No node executable found" in result.stderr

    def test_the_version_check_file_is_cleaned_up(
        self, launcher: Path, tmp_path: Path
    ) -> None:
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        run(launcher, "-V", env=os.environ | {"TEMP": str(temp_dir)})

        assert list(temp_dir.glob("__pyodide_node_check_*")) == []


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
        # we report it as an Emscripten path, so match only the name
        assert result.stdout.strip().endswith("python.exe")

    @pytest.mark.parametrize(
        "code, expected",
        [
            ("print('exclamation!')", "exclamation!"),
            ("print('a!b!c')", "a!b!c"),
            ("print(1 & 2)", "0"),
            ("print('one two')", "one two"),
            ("print('pipe | caret ^')", "pipe | caret ^"),
            ("print('percent 50%')", "percent 50%"),
            ('print("percent 50%")', "percent 50%"),
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
