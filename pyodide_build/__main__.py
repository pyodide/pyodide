#!/usr/bin/env python3
import argparse

from . import buildall
from . import buildpkg
from . import pywasmcross


def main():
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(help='action')

    for command_name, module in (("buildpkg", buildpkg),
                                 ("buildall", buildall),
                                 ("pywasmcross", pywasmcross)):
        parser = module.make_parser(subparsers.add_parser(command_name))
        parser.set_defaults(func=module.main)

    args = main_parser.parse_args()
    # run the selected action
    args.func(args)


if __name__ == '__main__':
    main()
