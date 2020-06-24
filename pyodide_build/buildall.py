#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import argparse
import json
from pathlib import Path
import shutil

from . import common
from . import buildpkg


def build_package(pkgname, dependencies, packagesdir, outputdir, args):
    reqs = dependencies[pkgname]
    # Make sure all of the package's requirements are built first
    for req in reqs:
        build_package(req, dependencies, packagesdir, outputdir, args)
    buildpkg.build_package(packagesdir / pkgname / 'meta.yaml', args)
    shutil.copyfile(
        packagesdir / pkgname / 'build' / (pkgname + '.data'),
        outputdir / (pkgname + '.data'))
    shutil.copyfile(
        packagesdir / pkgname / 'build' / (pkgname + '.js'),
        outputdir / (pkgname + '.js'))


def build_packages(packagesdir, outputdir, args):
    # We have to build the packages in the correct order (dependencies first),
    # so first load in all of the package metadata and build a dependency map.
    dependencies = {}
    import_name_to_package_name = {}
    included_packages = common._parse_package_subset(args.only)
    if included_packages is not None:
        # check that the specified packages exist
        for name in included_packages:
            if not (packagesdir / name).exists():
                raise ValueError(
                    f'package name {name} does not exist. '
                    f'The value of PYODIDE_PACKAGES is likely incorrect.'
                )

    for pkgdir in packagesdir.iterdir():
        if (
            included_packages is not None
            and pkgdir.name not in included_packages
        ):
            print(
                f"Warning: skiping build of {pkgdir.name} due "
                f"to specified PYODIDE_PACKAGES"
            )
            continue

        pkgpath = pkgdir / 'meta.yaml'
        if pkgdir.is_dir() and pkgpath.is_file():
            pkg = common.parse_package(pkgpath)
            name = pkg['package']['name']
            reqs = pkg.get('requirements', {}).get('run', [])
            dependencies[name] = reqs
            imports = pkg.get('test', {}).get('imports', [name])
            for imp in imports:
                import_name_to_package_name[imp] = name

    for pkgname in dependencies.keys():
        build_package(pkgname, dependencies, packagesdir, outputdir, args)

    # The "test" package is built in a different way, so we hardcode its
    # existence here.
    dependencies['test'] = []

    # This is done last so the Makefile can use it as a completion token.
    with open(outputdir / 'packages.json', 'w') as fd:
        json.dump({
            'dependencies': dependencies,
            'import_name_to_package_name': import_name_to_package_name,
        }, fd)


def make_parser(parser):
    parser.description = (
        "Build all of the packages in a given directory\n\n"
        "Unless the --only option is provided"
    )
    parser.add_argument(
        'dir', type=str, nargs=1,
        help='Input directory containing a tree of package definitions')
    parser.add_argument(
        'output', type=str, nargs=1,
        help='Output directory in which to put all built packages')
    parser.add_argument(
        '--package_abi', type=int, required=True,
        help='The ABI number for the packages to be built')
    parser.add_argument(
        '--cflags', type=str, nargs='?', default=common.DEFAULTCFLAGS,
        help='Extra compiling flags')
    parser.add_argument(
        '--ldflags', type=str, nargs='?', default=common.DEFAULTLDFLAGS,
        help='Extra linking flags')
    parser.add_argument(
        '--host', type=str, nargs='?', default=common.HOSTPYTHON,
        help='The path to the host Python installation')
    parser.add_argument(
        '--target', type=str, nargs='?', default=common.TARGETPYTHON,
        help='The path to the target Python installation')
    parser.add_argument(
        '--only', type=str, nargs='?', default=None,
        help=('Only build the specified packages, provided as a comma '
              'separated list'))
    return parser


def main(args):
    packagesdir = Path(args.dir[0]).resolve()
    outputdir = Path(args.output[0]).resolve()
    build_packages(packagesdir, outputdir, args)


if __name__ == '__main__':
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
