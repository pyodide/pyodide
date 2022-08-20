import argparse
import os

from .. import common, pypabuild, pywasmcross


def run(exports, args):
    cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    build_env_ctx = pywasmcross.get_build_env(
        env=os.environ.copy(),
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        exports=exports,
    )

    with build_env_ctx as env:
        pypabuild.build(env, " ".join(args))


def main(parser_args: argparse.Namespace) -> None:
    common.check_emscripten_version()
    run(parser_args.exports, parser_args.backend_args)


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Use pypa/build to build a Python package."
    parser.add_argument(
        "--exports",
        choices=["pyinit", "requested", "whole_archive"],
        default="requested",
        help="Which symbols should be exported when linking .so files?",
    )
    parser.add_argument(
        "backend_args",
        metavar="args",
        type=str,
        nargs=argparse.REMAINDER,
        help="Arguments to pass on to the backend",
    )
    return parser
