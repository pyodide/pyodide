import subprocess

import pytest


def _fake_check_output(args, encoding=None) -> str:
    """A fake subprocess.call_output function"""
    if args[:2] == ["git", "merge-base"]:
        assert args[2] == "origin/master"
        assert args[3] == "HEAD"
        return "9207111c967"
    elif args[:3] == ["git", "diff", "--name-only"]:
        return "src/file1.py\nsetup.py"
    else:
        raise AssertionError


def test_git_get_files_changed(monkeypatch):
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr(subprocess, "check_output", _fake_check_output)
    from pyodide_build.ci_job_required import git_get_files_changed

    file_names = git_get_files_changed()
    assert file_names == ["src/file1.py", "setup.py"]


@pytest.mark.parametrize(
    "files_changed, needs_core, needs_packages",
    [
        (["Makefile"], True, True),
        (["docs/conf.py"], False, False),
        (["packages/numpy/meta.yaml", "src/pyodide.js"], True, True),
        (["src/tests/test_bz2.py"], True, False),
    ],
)
def test_ci_job_required(files_changed, needs_core, needs_packages):
    from pyodide_build.ci_job_required import check_ci_job_required

    assert check_ci_job_required("build_core", files_changed) is needs_core
    assert check_ci_job_required("build_packages", files_changed) is needs_packages
