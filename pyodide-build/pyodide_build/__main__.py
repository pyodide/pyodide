#!/usr/bin/env python3
import argparse
import sys

from . import (
    buildall,
    buildpkg,
    create_xbuildenv,
    install_xbuildenv,
    mkpkg,
    serve,
    wrapper,
)
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
        ("create_xbuildenv", create_xbuildenv),
        ("install_xbuildenv", install_xbuildenv),
        ("wrapper", wrapper),
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


def main() -> None:
    init_environment()

    main_parser = make_parser()

    args = main_parser.parse_args()
    if hasattr(args, "func"):
        # run the selected action
        args.func(args)
    else:
        main_parser.print_help()


def out_of_tree_main():
    import os
    from pathlib import Path

    env_str = ".pyodide-xbuildenv"
    env = Path(env_str)
    os.environ["PYODIDE_ROOT"] = env_str
    if not env.exists():
        from .install_xbuildenv import download_xbuild_env, install_xbuild_env
        download_xbuild_env(env)
        install_xbuild_env(env)

    from .wrapper import run
    import sys
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
