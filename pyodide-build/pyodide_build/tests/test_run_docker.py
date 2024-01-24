import os
import subprocess
from pathlib import Path

PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT")
if PYODIDE_ROOT:
    PYODIDE_ROOT = Path(PYODIDE_ROOT)
else:
    from pyodide_build import build_env
    PYODIDE_ROOT = build_env.search_pyodide_root(os.getcwd())


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
