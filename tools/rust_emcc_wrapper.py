#!/usr/bin/env python3
import subprocess
import sys


def update_args(args):
    # https://github.com/emscripten-core/emscripten/issues/17109
    args.insert(0, "-Wl,--no-whole-archive")

    # Remove -s ASSERTIONS=1
    # See https://github.com/rust-lang/rust/pull/97928
    for i in range(len(args)):
        if "ASSERTIONS" in args[i]:
            del args[i - 1 : i + 1]
            break

    # remove -lc
    # https://github.com/emscripten-core/emscripten/issues/17191
    for i in range(len(args)):
        if args[i] == "c" and args[i - 1] == "-l":
            del args[i - 1 : i + 1]

    return args


def main(args):
    args = update_args(args)
    return subprocess.call(["emcc"] + args)


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(args))
