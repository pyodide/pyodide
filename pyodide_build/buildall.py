#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import argparse
from functools import total_ordering
import json
from pathlib import Path
from queue import Queue, PriorityQueue
import shutil
import subprocess
import sys
from threading import Thread
from time import sleep
from typing import Dict, Set, Optional, List

from . import common


@total_ordering
class Package:
    def __init__(self, pkgdir: Path):
        self.pkgdir = pkgdir

        pkgpath = pkgdir / "meta.yaml"
        if not pkgpath.is_file():
            raise ValueError(f"Directory {pkgdir} does not contain meta.yaml")

        self.meta: dict = common.parse_package(pkgpath)
        self.name: str = self.meta["package"]["name"]

        assert self.name == pkgdir.stem

        self.dependencies: List[str] = self.meta.get("requirements", {}).get("run", [])
        self.unbuilt_dependencies: Set[str] = set(self.dependencies)
        self.dependents: Set[str] = set()

    def build(self, outputdir: Path, args):
        with open(self.pkgdir / "build.log", "w") as f:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pyodide_build",
                    "buildpkg",
                    str(self.pkgdir / "meta.yaml"),
                    "--package_abi",
                    str(args.package_abi),
                    "--cflags",
                    args.cflags,
                    "--ldflags",
                    args.ldflags,
                    "--target",
                    args.target,
                    "--install-dir",
                    args.install_dir,
                ],
                check=True,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        with open(self.pkgdir / "build.log", "r") as f:
            for line in f:
                print(line)

        shutil.copyfile(
            self.pkgdir / "build" / (self.name + ".data"),
            outputdir / (self.name + ".data"),
        )
        shutil.copyfile(
            self.pkgdir / "build" / (self.name + ".js"),
            outputdir / (self.name + ".js"),
        )

    # We use this in the priority queue, which pops off the smallest element.
    # So we want the smallest element to have the largest number of dependents
    def __lt__(self, other):
        return len(self.dependents) > len(other.dependents)

    def __eq__(self, other):
        return len(self.dependents) == len(other.dependents)


# The strategy for building packages is as follows --- we have a set of
# packages that we eventually want to build, each represented by a Package
# object defined above. Each package remembers the list of all packages that
# depend on it (pkg.dependents) and all its dependencies that are not yet
# built (pkg.dependencies).
#
# We keep a list of packages we are ready to build (to_build). Iteratively, we
#
#  - pop a package off the list
#  - build it
#  - for each dependent, remove the current package from the list of unbuilt
#    dependencies. If all dependencies of the dependent have been built, add
#    the dependent to to_build
#
# We keep iterating until to_build is empty. When it is empty, if there are no
# circular dependencies, then all packages should have been built, which we
# check with an assert just to be sure.
def build_packages(packagesdir, outputdir, args):
    pkg_map: Dict[str, Package] = {}

    packages: Optional[Set[str]] = common._parse_package_subset(args.only)
    if packages is None:
        packages = set(
            str(x) for x in packagesdir.iterdir() if (x / "meta.yaml").is_file()
        )

    # Generate Package objects for all specified packages and recursive
    # dependencies.
    while packages:
        pkgname = packages.pop()
        if pkg_map.get(pkgname) is not None:
            continue

        pkg = Package(packagesdir / pkgname)
        pkg_map[pkg.name] = pkg

        for dep in pkg.dependencies:
            # This won't catch all duplicates but let's try our best
            if pkg_map.get(dep) is None:
                packages.add(dep)

    # Build set of dependents
    for pkg in pkg_map.values():
        for dep in pkg.dependencies:
            pkg_map[dep].dependents.add(pkg.name)

    # Insert packages into build_queue. We *must* do this after counting
    # dependents, because the ordering ought not to change after insertion.
    build_queue: PriorirtyQueue = PriorityQueue()
    for pkg in pkg_map.values():
        if len(pkg.dependencies) == 0:
            build_queue.put(pkg)

    built_queue = Queue()

    def builder(n):
        print(f"Starting thread {n}")
        while True:
            pkg = build_queue.get()
            print(f"Thread {n} building {pkg.name}")
            pkg.build(outputdir, args)
            print(f"Thread {n} built {pkg.name}")
            built_queue.put(pkg)
            sleep(0.01)

    threads = [
        Thread(target=builder, daemon=True, args=(n,)).start() for n in range(0, 4)
    ]

    num_built = 0
    while num_built < len(pkg_map):
        pkg = built_queue.get()
        num_built += 1

        for dependent in pkg.dependents:
            dependent = pkg_map[dependent]
            dependent.unbuilt_dependencies.remove(pkg.name)
            if len(dependent.unbuilt_dependencies) == 0:
                # Due to to GIL, all packages will be added before a package
                # gets picked up by a thread, so it correctly compiles the most
                # prioritized one.
                build_queue.put(dependent)

    assert len(pkg_map) == num_built

    # Build package.json data. The "test" package is built in a different way,
    # so we hardcode its existence here.
    #
    # This is done last so the Makefile can use it as a completion token.
    package_data = {
        "dependencies": {"test": []},
        "import_name_to_package_name": {},
    }

    for name, pkg in pkg_map.items():
        package_data["dependencies"][name] = pkg.dependencies
        for imp in pkg.meta.get("test", {}).get("imports", [name]):
            package_data["import_name_to_package_name"][imp] = name

    with open(outputdir / "packages.json", "w") as fd:
        json.dump(package_data, fd)


def make_parser(parser):
    parser.description = (
        "Build all of the packages in a given directory\n\n"
        "Unless the --only option is provided"
    )
    parser.add_argument(
        "dir",
        type=str,
        nargs=1,
        help="Input directory containing a tree of package definitions",
    )
    parser.add_argument(
        "output",
        type=str,
        nargs=1,
        help="Output directory in which to put all built packages",
    )
    parser.add_argument(
        "--package_abi",
        type=int,
        required=True,
        help="The ABI number for the packages to be built",
    )
    parser.add_argument(
        "--cflags",
        type=str,
        nargs="?",
        default=common.DEFAULTCFLAGS,
        help="Extra compiling flags",
    )
    parser.add_argument(
        "--ldflags",
        type=str,
        nargs="?",
        default=common.DEFAULTLDFLAGS,
        help="Extra linking flags",
    )
    parser.add_argument(
        "--target",
        type=str,
        nargs="?",
        default=common.TARGETPYTHON,
        help="The path to the target Python installation",
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        nargs="?",
        default="",
        help=(
            "Directory for installing built host packages. Defaults to setup.py "
            "default. Set to 'skip' to skip installation. Installation is "
            "needed if you want to build other packages that depend on this one."
        ),
    )
    parser.add_argument(
        "--only",
        type=str,
        nargs="?",
        default=None,
        help=(
            "Only build the specified packages, provided as a comma " "separated list"
        ),
    )
    parser.add_argument(
        "--num-threads", type=str, nargs="?", default=4, help="Number of threads to use"
    )
    return parser


def main(args):
    packagesdir = Path(args.dir[0]).resolve()
    outputdir = Path(args.output[0]).resolve()
    build_packages(packagesdir, outputdir, args)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
