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

    # remove -lc. Not sure if it makes a difference but -lc doesn't belong here.
    # https://github.com/emscripten-core/emscripten/issues/17191
    for i in reversed(range(len(args))):
        if args[i] == "c" and args[i - 1] == "-l":
            del args[i - 1 : i + 1]

    # Prevent a bunch of errors caused by buggy behavior in
    # `esmcripten/tools/building.py:lld_flags_for_executable` REQUIRED_EXPORTS
    # contains symbols that should come from the main module.
    # https://github.com/emscripten-core/emscripten/issues/17202
    args.append("-sERROR_ON_UNDEFINED_SYMBOLS=0")
    # Seems like --no-entry should be implied by SIDE_MODULE but apparently it
    # isn't?
    args.append("-Wl,--no-entry")
    # Without this, the dylink section seems to get deleted which causes trouble
    # at load time.
    args.append("-Wl,--no-gc-sections")

    return args


def main(args):
    args = update_args(args)
    return subprocess.call(["emcc"] + args)


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(main(args))
