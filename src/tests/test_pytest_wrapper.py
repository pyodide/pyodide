import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2] / "tools"))

from pytest_wrapper import remove_num_threads_option


def test_find_imports():
    args = ["-v", "-n", "3"]
    remove_num_threads_option(args)
    assert args == ["-v"]

    args = ["-v", "-n", "3", "-k", "firefox"]
    remove_num_threads_option(args)
    assert args == ["-v", "-k", "firefox"]
