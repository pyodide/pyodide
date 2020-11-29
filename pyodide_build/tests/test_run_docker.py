from pathlib import Path
import subprocess

BASE_DIR = Path(__file__).parents[2]


def test_run_docker_script():
    res = subprocess.run(
        ["bash", str(BASE_DIR / "run_docker"), "--help"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "Usage:\n  run_docker" in res.stdout.decode("utf-8")

    res = subprocess.run(
        ["bash", str(BASE_DIR / "run_docker"), "--invalid-param"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert res.returncode > 0
    assert "Unknown option --invalid-param" in res.stderr.decode("utf-8")
