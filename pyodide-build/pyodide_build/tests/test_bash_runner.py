import subprocess
from pathlib import Path

from pyodide_build import bash_runner


def test_subprocess_with_shared_env_1():
    with bash_runner.BashRunnerWithSharedEnvironment() as p:
        p.env.pop("A", None)

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) is None

        p.run_unchecked("export A=2")
        assert p.env["A"] == "2"

        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "2\n"

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) == "6"

        p.env["A"] = "7"
        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "7\n"
        assert p.env["A"] == "7"


def test_subprocess_with_shared_env_cwd(tmp_path: Path) -> None:
    src_dir = tmp_path / "build/package_name"
    src_dir.mkdir(parents=True)
    script = "touch out.txt"
    with bash_runner.BashRunnerWithSharedEnvironment() as shared_env:
        shared_env.run_unchecked(script, cwd=src_dir)
        assert (src_dir / "out.txt").exists()


def test_subprocess_with_shared_env_logging(capfd, tmp_path):
    from pytest import raises

    with bash_runner.BashRunnerWithSharedEnvironment() as p:
        p.run("echo 1000", script_name="a test script")
        cap = capfd.readouterr()
        assert [l.strip() for l in cap.out.splitlines()] == [
            f"Running a test script in {Path.cwd()}",
            "1000",
        ]
        assert cap.err == ""

        dir = tmp_path / "a"
        dir.mkdir()
        p.run("echo 1000", script_name="test script", cwd=dir)
        cap = capfd.readouterr()
        assert [l.strip() for l in cap.out.splitlines()] == [
            "Running test script in",
            str(dir),
            "1000",
        ]
        assert cap.err == ""

        dir = tmp_path / "b"
        dir.mkdir()
        with raises(SystemExit) as e:
            p.run("exit 7", script_name="test2 script", cwd=dir)
        cap = capfd.readouterr()
        assert e.value.args[0] == 7
        assert [l.strip() for l in cap.out.splitlines()] == [
            "Running test2 script in",
            str(dir),
        ]
        assert [l.strip() for l in cap.err.splitlines()] == [
            "ERROR: test2 script failed",
            "exit 7",
        ]
