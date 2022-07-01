import argparse
import os
import subprocess
import sys
from typing import NoReturn

from . import common, pypabuild, pywasmcross


def run(args: list[str]):
    cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    build_env_ctx = pywasmcross.get_build_env(
        env=os.environ,
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        replace_libs="",
        exports="requested",
    )

    with build_env_ctx as env:
        pypabuild.build(env, " ".join(args))
        # import pprint
        # pprint.pprint(env)
        # sys.exit(subprocess.run(args, env=env).returncode)


def main(parser_args: argparse.Namespace):
    run(parser_args.args)


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Build a pyodide package.\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the Pyodide Makefile."
    )
    parser.add_argument(
        "args",
        metavar="args",
        type=str,
        nargs=argparse.REMAINDER,
        help="command to run",
    )
    return parser
