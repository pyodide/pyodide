#!/usr/bin/env python3

import os
import subprocess
import sys

args = sys.argv[1:]


def remove_num_threads_option(args: list[str]) -> None:
    """Remove -n <n> from argument list"""
    for i in range(0, len(args)):
        if args[i] == "-n":
            del args[i : i + 2]
            break


def cache_dir(args: list[str]) -> None:
    """Find the name of the cache-dir in the argument list"""
    for i in range(0, len(args)):
        if args[i] == "-o" and args[i + 1].startswith("cache_dir"):
            return args[i + 1].split("=")[1]
            break
    return ".pytest_cache"


if __name__ == "__main__":
    try:
        subprocess.run([sys.executable, "-m", "pytest"] + args, check=True)
        sys.exit(0)
    except subprocess.CalledProcessError:
        pass

    # Failed tests. Look up number of failed tests
    lastfailed_path = os.path.join(cache_dir(args), "v/cache/lastfailed")
    if not os.path.exists(lastfailed_path):
        print("Test failed during collection. Not rerunning.")
        sys.exit(1)
    with open(lastfailed_path) as f:
        num_failed = sum(1 for line in f) - 2

    if num_failed > 9:
        print("More than 9 tests failed. Not rerunning")
        sys.exit(1)

    print("Rerunning failed tests sequentially")
    remove_num_threads_option(args)
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--lf"] + args, check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)
