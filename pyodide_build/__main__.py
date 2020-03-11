#!/usr/bin/env python3
import argparse

from . import buildall
from . import buildpkg
from . import pywasmcross
from . import serve
from . import mkpkg


def main():
    main_parser = argparse.ArgumentParser(prog='pyodide')
    subparsers = main_parser.add_subparsers(help='action')

    for command_name, module in (("buildpkg", buildpkg),
                                 ("buildall", buildall),
                                 ("pywasmcross", pywasmcross),
                                 ("serve", serve),
                                 ("mkpkg", mkpkg)):
        parser = module.make_parser(subparsers.add_parser(command_name))
        parser.set_defaults(func=module.main)

    args = main_parser.parse_args()
    if hasattr(args, 'func'):
        # run the selected action
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == '__main__':
    main()
