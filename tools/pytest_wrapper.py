#!/usr/bin/env python3

import subprocess
from typing import List
import sys

args = sys.argv[1:]


def clean_args(args: List[str]) -> None:
    """Remove -n <n> from argument list"""
    for i in range(0, len(args)):
        if args[i] == "-n":
            del args[i : i + 2]
            break


if __name__ == "__main__":
    try:
        subprocess.run(["pytest"] + args, check=True)
    except subprocess.CalledProcessError:
        # Failed tests. Look up number of failed tests
        with open(".pytest_cache/v/cache/lastfailed") as f:
            num_failed = sum(1 for line in f) - 2

        if num_failed < 10:
            print("Rerunnning failed tests sequentially")
            clean_args(args)
            subprocess.run(["pytest", "--lf"] + args, check=True)
        else:
            print("More than 9 tests failed. Not rerunning")
            raise
