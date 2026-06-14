#!/usr/bin/env python3

import os
import platform
import subprocess
import sys
import time

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


def is_safari_run(args: list[str]) -> bool:
    for arg in args:
        if "safari" in arg.lower():
            return True
    return False


def cleanup_safari() -> None:
    if platform.system() != "Darwin":
        return
    print("Cleaning up Safari/safaridriver processes before retry...")
    subprocess.run(["pkill", "-9", "Safari"], capture_output=True, check=False)
    subprocess.run(["pkill", "-9", "safaridriver"], capture_output=True, check=False)
    time.sleep(3)


if __name__ == "__main__":
    try:
        subprocess.run([sys.executable, "-m", "pytest"] + args, check=True)
        sys.exit(0)
    except subprocess.CalledProcessError:
        pass

    lastfailed_path = os.path.join(cache_dir(args), "v/cache/lastfailed")
    if not os.path.exists(lastfailed_path):
        print("Test failed during collection. Not rerunning.")
        sys.exit(1)
    with open(lastfailed_path) as f:
        num_failed = sum(1 for line in f) - 2

    if num_failed > 9:
        print("More than 9 tests failed. Not rerunning")
        sys.exit(1)

    if is_safari_run(args):
        cleanup_safari()

    print("Rerunning failed tests sequentially")
    remove_num_threads_option(args)
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--lf"] + args, check=True)
    except subprocess.CalledProcessError:
        sys.exit(1)
