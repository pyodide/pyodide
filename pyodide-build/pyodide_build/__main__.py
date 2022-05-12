#!/usr/bin/env python3
import argparse
import sys

from . import buildall, buildpkg, mkpkg, serve
from .common import init_environment


def make_parser() -> argparse.ArgumentParser:
    """Create an argument parser with argparse"""

    main_parser = argparse.ArgumentParser(prog="pyodide")
    main_parser.description = "A command line interface (CLI) for pyodide_build"
    subparsers = main_parser.add_subparsers(help="action")

    for command_name, module in (
        ("buildpkg", buildpkg),
        ("buildall", buildall),
        ("serve", serve),
        ("mkpkg", mkpkg),
    ):
        if "sphinx" in sys.modules and command_name in [
            "buildpkg",
            "buildall",
            "pywasmcross",
        ]:
            # Likely building documentation, skip private API
            continue
        parser = module.make_parser(subparsers.add_parser(command_name))
        parser.set_defaults(func=module.main)
    return main_parser


def main():
    init_environment()

    main_parser = make_parser()

    args = main_parser.parse_args()
    if hasattr(args, "func"):
        # run the selected action
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == "__main__":
    main()
