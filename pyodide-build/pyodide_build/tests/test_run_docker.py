import os
import subprocess
from pathlib import Path

if "PYODIDE_ROOT" in os.environ:
    PYODIDE_ROOT = Path(os.environ["PYODIDE_ROOT"])
else:
    from pyodide_build import build_env

    PYODIDE_ROOT = build_env.search_pyodide_root(Path.cwd())


def test_run_docker_script():
    res = subprocess.run(
        ["bash", str(PYODIDE_ROOT / "run_docker"), "--help"],
        check=False,
        capture_output=True,
    )

    assert "Usage: run_docker" in res.stdout.decode("utf-8")

    res = subprocess.run(
        ["bash", str(PYODIDE_ROOT / "run_docker"), "--invalid-param"],
        check=False,
        capture_output=True,
    )
    assert res.returncode > 0
    assert "Unknown option --invalid-param" in res.stderr.decode("utf-8")
