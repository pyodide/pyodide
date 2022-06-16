#!/usr/bin/env python3
import subprocess
import sys


def update_args(args):
    # remove -lc. Not sure if it makes a difference but -lc doesn't belong here.
    # https://github.com/emscripten-core/emscripten/issues/17191
    for i in reversed(range(len(args))):
        if args[i] == "c" and args[i - 1] == "-l":
            del args[i - 1 : i + 1]

    return args


def main(args):
    args = update_args(args)
    return subprocess.call(["emcc"] + args)


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(args))
