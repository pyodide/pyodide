import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2] / "tools"))

from pytest_wrapper import clean_args


def test_find_imports():
    args = ["-v", "-n", "3"]
    clean_args(args)
    assert args == ["-v"]

    args = ["-v", "-n", "3", "-k", "firefox"]
    clean_args(args)
    assert args == ["-v", "-k", "firefox"]
