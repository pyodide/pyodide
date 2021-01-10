#!/usr/bin/env python3

import subprocess
from typing import List
import sys

EXTRA_ARGS = ["-v", "-r", "fE"]
args = EXTRA_ARGS + sys.argv[1:]


def clean_args(args: List[str]) -> None:
    """Remove -n <n> from argument list"""
    for i in range(0, len(args)):
        if args[i] == "-n":
            del args[i : i + 2]
            break


if __name__ == "__main__":
    try:
        subprocess.run(["pytest"] + args, check=True)
        sys.exit(0)
    except subprocess.CalledProcessError:
        pass

    # Failed tests. Look up number of failed tests
    with open(".pytest_cache/v/cache/lastfailed") as f:
        num_failed = sum(1 for line in f) - 2

    if num_failed > 9:
        print("More than 9 tests failed. Not rerunning")
        sys.exit(1)

    print("Rerunnning failed tests sequentially")
    clean_args(args)
    try:
        subprocess.run(["pytest", "--lf"] + args, check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)
