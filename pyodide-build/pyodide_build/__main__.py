#!/usr/bin/env python3
import argparse
import os
import sys

from . import buildall, buildpkg, mkpkg, serve
from .common import get_hostsitepackages, get_make_environment_vars


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
    if not os.environ.get("__LOADED_PYODIDE_ENV"):
        if "PYODIDE_ROOT" not in os.environ:
            # If we are building docs or running tests, we don't need to know the PYODIDE_ROOT
            if "sphinx" not in sys.modules and "pytest" not in sys.modules:
                raise ValueError(
                    "PYODIDE_ROOT needs to be set. Try export `PYODIDE_ROOT=<pyodide-root-directory>` then rerun."
                )

        os.environ.update(get_make_environment_vars())
        hostsitepackages = get_hostsitepackages()
        pythonpath = [
            hostsitepackages,
        ]
        os.environ["PYTHONPATH"] = ":".join(pythonpath)
        os.environ["BASH_ENV"] = ""
        os.environ["__LOADED_PYODIDE_ENV"] = "1"

    main_parser = make_parser()

    args = main_parser.parse_args()
    if hasattr(args, "func"):
        # run the selected action
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == "__main__":
    main()
