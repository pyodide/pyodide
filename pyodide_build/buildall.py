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
from time import sleep, perf_counter
from typing import Dict, Set, Optional, List

from . import common
from .io import parse_package_config
from .common import UNVENDORED_STDLIB_MODULES


class BasePackage:
    pkgdir: Path
    name: str
    version: str
    meta: dict
    library: bool
    shared_library: bool
    dependencies: List[str]
    unbuilt_dependencies: Set[str]
    dependents: Set[str]

    # We use this in the priority queue, which pops off the smallest element.
    # So we want the smallest element to have the largest number of dependents
    def __lt__(self, other) -> bool:
        return len(self.dependents) > len(other.dependents)

    def __eq__(self, other) -> bool:
        return len(self.dependents) == len(other.dependents)


@total_ordering
class StdLibPackage(BasePackage):
    def __init__(self, pkgdir: Path):
        self.pkgdir = pkgdir
        self.meta = {}
        self.name = pkgdir.stem
        self.version = "1.0"
        self.library = False
        self.shared_library = False
        self.dependencies = []
        self.unbuilt_dependencies = set()
        self.dependents = set()

    def build(self, outputdir: Path, args) -> None:
        # All build / packaging steps are already done in the main Makefile
        return


@total_ordering
class Package(BasePackage):
    def __init__(self, pkgdir: Path):
        self.pkgdir = pkgdir

        pkgpath = pkgdir / "meta.yaml"
        if not pkgpath.is_file():
            raise ValueError(f"Directory {pkgdir} does not contain meta.yaml")

        self.meta = parse_package_config(pkgpath)
        self.name = self.meta["package"]["name"]
        self.version = self.meta["package"]["version"]
        self.library = self.meta.get("build", {}).get("library", False)
        self.shared_library = self.meta.get("build", {}).get("sharedlibrary", False)

        assert self.name == pkgdir.stem

        self.dependencies = self.meta.get("requirements", {}).get("run", [])
        self.unbuilt_dependencies = set(self.dependencies)
        self.dependents = set()

    def build(self, outputdir: Path, args) -> None:
        with open(self.pkgdir / "build.log", "w") as f:
            p = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pyodide_build",
                    "buildpkg",
                    str(self.pkgdir / "meta.yaml"),
                    "--cflags",
                    args.cflags,
                    "--cxxflags",
                    args.cxxflags,
                    "--ldflags",
                    args.ldflags,
                    "--target",
                    args.target,
                    "--install-dir",
                    args.install_dir,
                ],
                check=False,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        try:
            p.check_returncode()
        except subprocess.CalledProcessError:
            print(f"Error building {self.name}. Printing build logs.")

            with open(self.pkgdir / "build.log", "r") as f:
                shutil.copyfileobj(f, sys.stdout)

            raise

        if not self.library:
            shutil.copyfile(
                self.pkgdir / "build" / (self.name + ".data"),
                outputdir / (self.name + ".data"),
            )
            shutil.copyfile(
                self.pkgdir / "build" / (self.name + ".js"),
                outputdir / (self.name + ".js"),
            )


def generate_dependency_graph(
    packages_dir: Path, package_list: Optional[str]
) -> Dict[str, BasePackage]:
    """
    This generates a dependency graph for the packages listed in package_list.
    A node in the graph is a BasePackage object defined above, which maintains
    a list of dependencies and also dependents. That is, each node stores both
    incoming and outgoing edges.

    The dependencies and dependents are stored via their name, and we have a
    lookup table pkg_map: Dict[str, BasePackage] to look up the corresponding
    BasePackage object. The function returns pkg_map, which contains all
    packages in the graph as its values.

    Parameters:
     - packages_dir: directory that contains packages
     - package_list: set of packages to build. If None, then all packages in
       packages_dir are compiled.

    Returns:
     - pkg_map: dictionary mapping package names to BasePackage objects
    """

    pkg_map: Dict[str, BasePackage] = {}

    packages: Optional[Set[str]] = common._parse_package_subset(package_list)
    if packages is None:
        packages = set(
            str(x) for x in packages_dir.iterdir() if (x / "meta.yaml").is_file()
        )

    while packages:
        pkgname = packages.pop()

        pkg: BasePackage
        if pkgname in UNVENDORED_STDLIB_MODULES:
            pkg = StdLibPackage(packages_dir / pkgname)
        else:
            pkg = Package(packages_dir / pkgname)
        pkg_map[pkg.name] = pkg

        for dep in pkg.dependencies:
            if pkg_map.get(dep) is None:
                packages.add(dep)

    # Compute dependents
    for pkg in pkg_map.values():
        for dep in pkg.dependencies:
            pkg_map[dep].dependents.add(pkg.name)

    return pkg_map


def build_from_graph(pkg_map: Dict[str, BasePackage], outputdir: Path, args) -> None:
    """
    This builds packages in pkg_map in parallel, building at most args.n_jobs
    packages at once.

    We have a priority queue of packages we are ready to build (build_queue),
    where a package is ready to build if all its dependencies are built. The
    priority is based on the number of dependents --- we prefer to build
    packages with more dependents first.

    To build packages in parallel, we use a thread pool of args.n_jobs many
    threads listening to build_queue. When the thread is free, it takes an
    item off build_queue and builds it. Once the package is built, it sends the
    package to the built_queue. The main thread listens to the built_queue and
    checks if any of the dependents are ready to be built. If so, it add the
    package to the build queue.
    """

    # Insert packages into build_queue. We *must* do this after counting
    # dependents, because the ordering ought not to change after insertion.
    build_queue: PriorityQueue = PriorityQueue()
    for pkg in pkg_map.values():
        if len(pkg.dependencies) == 0:
            build_queue.put(pkg)

    built_queue: Queue = Queue()

    def builder(n):
        print(f"Starting thread {n}")
        while True:
            pkg = build_queue.get()

            print(f"Thread {n} building {pkg.name}")
            t0 = perf_counter()
            try:
                pkg.build(outputdir, args)
            except Exception as e:
                built_queue.put(e)
                return

            print(f"Thread {n} built {pkg.name} in {perf_counter() - t0:.1f} s")
            built_queue.put(pkg)
            # Release the GIL so new packages get queued
            sleep(0.01)

    for n in range(0, args.n_jobs):
        Thread(target=builder, args=(n + 1,), daemon=True).start()

    num_built = 0
    while num_built < len(pkg_map):
        pkg = built_queue.get()
        if isinstance(pkg, Exception):
            raise pkg

        num_built += 1

        for _dependent in pkg.dependents:
            dependent = pkg_map[_dependent]
            dependent.unbuilt_dependencies.remove(pkg.name)
            if len(dependent.unbuilt_dependencies) == 0:
                build_queue.put(dependent)


def build_packages(packages_dir: Path, outputdir: Path, args) -> None:
    pkg_map = generate_dependency_graph(packages_dir, args.only)

    build_from_graph(pkg_map, outputdir, args)

    # Build package.json data.
    package_data: dict = {
        "dependencies": {key: [] for key in UNVENDORED_STDLIB_MODULES},
        "import_name_to_package_name": {},
        "shared_library": {},
        "versions": {},
    }

    libraries = [pkg.name for pkg in pkg_map.values() if pkg.library]

    for name, pkg in pkg_map.items():
        if pkg.library:
            continue
        if pkg.shared_library:
            package_data["shared_library"][name] = True
        package_data["dependencies"][name] = [
            x for x in pkg.dependencies if x not in libraries
        ]
        package_data["versions"][name] = pkg.version
        for imp in pkg.meta.get("test", {}).get("imports", [name]):
            package_data["import_name_to_package_name"][imp] = name

    # Hack for 0.17.0 release
    # TODO: FIXME!!
    if "soupsieve" in pkg_map:
        package_data["dependencies"]["soupsieve"].append("beautifulsoup4")
    with open(outputdir / "packages.json", "w") as fd:
        json.dump(package_data, fd)


def make_parser(parser):
    parser.description = (
        "Build all of the packages in a given directory\n\n"
        "Unless the --only option is provided\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the pyodide Makefile."
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
        "--cflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_CFLAGS"),
        help="Extra compiling flags",
    )
    parser.add_argument(
        "--cxxflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_CXXFLAGS"),
        help="Extra C++ specific compiling flags",
    )
    parser.add_argument(
        "--ldflags",
        type=str,
        nargs="?",
        default=common.get_make_flag("SIDE_MODULE_LDFLAGS"),
        help="Extra linking flags",
    )
    parser.add_argument(
        "--target",
        type=str,
        nargs="?",
        default=common.get_make_flag("TARGETPYTHONROOT"),
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
        help=("Only build the specified packages, provided as a comma-separated list"),
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        nargs="?",
        default=4,
        help="Number of packages to build in parallel",
    )
    return parser


def main(args):
    packages_dir = Path(args.dir[0]).resolve()
    outputdir = Path(args.output[0]).resolve()
    build_packages(packages_dir, outputdir, args)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
