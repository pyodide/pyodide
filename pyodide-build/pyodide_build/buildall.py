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
from threading import Thread, Lock
from time import sleep, perf_counter
from typing import Dict, Set, Optional, List, Any
import os

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
    unvendored_tests: Optional[bool] = None

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
        with open(self.pkgdir / "build.log.tmp", "w") as f:
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
                    "--target-install-dir",
                    args.target_install_dir,
                    "--host-install-dir",
                    args.host_install_dir,
                ],
                check=False,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        # Don't overwrite build log if we didn't build the file.
        # If the file didn't need to be rebuilt, the log will have exactly two lines.
        rebuilt = True
        with open(self.pkgdir / "build.log.tmp", "r") as f:
            try:
                next(f)
                next(f)
                next(f)
            except StopIteration:
                rebuilt = False

        if rebuilt:
            shutil.move(self.pkgdir / "build.log.tmp", self.pkgdir / "build.log")  # type: ignore
        else:
            (self.pkgdir / "build.log.tmp").unlink()

        if args.log_dir and (self.pkgdir / "build.log").exists():
            shutil.copy(
                self.pkgdir / "build.log", Path(args.log_dir) / f"{self.name}.log"
            )

        try:
            p.check_returncode()
        except subprocess.CalledProcessError:
            print(f"Error building {self.name}. Printing build logs.")

            with open(self.pkgdir / "build.log", "r") as f:
                shutil.copyfileobj(f, sys.stdout)

            raise

        if self.library:
            return
        shutil.copyfile(
            self.pkgdir / "build" / (self.name + ".data"),
            outputdir / (self.name + ".data"),
        )
        shutil.copyfile(
            self.pkgdir / "build" / (self.name + ".js"),
            outputdir / (self.name + ".js"),
        )
        if (self.pkgdir / "build" / (self.name + "-tests.data")).exists():
            shutil.copyfile(
                self.pkgdir / "build" / (self.name + "-tests.data"),
                outputdir / (self.name + "-tests.data"),
            )
            shutil.copyfile(
                self.pkgdir / "build" / (self.name + "-tests.js"),
                outputdir / (self.name + "-tests.js"),
            )


def generate_dependency_graph(
    packages_dir: Path, packages: Set[str]
) -> Dict[str, BasePackage]:
    """This generates a dependency graph for listed packages.

    A node in the graph is a BasePackage object defined above, which maintains
    a list of dependencies and also dependents. That is, each node stores both
    incoming and outgoing edges.

    The dependencies and dependents are stored via their name, and we have a
    lookup table pkg_map: Dict[str, BasePackage] to look up the corresponding
    BasePackage object. The function returns pkg_map, which contains all
    packages in the graph as its values.

    Parameters:
     - packages_dir: directory that contains packages
     - packages: set of packages to build. If None, then all packages in
       packages_dir are compiled.

    Returns:
     - pkg_map: dictionary mapping package names to BasePackage objects
    """

    pkg_map: Dict[str, BasePackage] = {}

    if "*" in packages:
        packages.discard("*")
        packages.update(
            str(x) for x in packages_dir.iterdir() if (x / "meta.yaml").is_file()
        )

    no_numpy_dependents = "no-numpy-dependents" in packages
    if no_numpy_dependents:
        packages.discard("no-numpy-dependents")

    while packages:
        pkgname = packages.pop()

        pkg: BasePackage
        if pkgname in UNVENDORED_STDLIB_MODULES:
            pkg = StdLibPackage(packages_dir / pkgname)
        else:
            pkg = Package(packages_dir / pkgname)
        if no_numpy_dependents and "numpy" in pkg.dependencies:
            continue
        pkg_map[pkg.name] = pkg

        for dep in pkg.dependencies:
            if pkg_map.get(dep) is None:
                packages.add(dep)

    # Compute dependents
    for pkg in pkg_map.values():
        for dep in pkg.dependencies:
            pkg_map[dep].dependents.add(pkg.name)

    return pkg_map


def job_priority(pkg: BasePackage):
    if pkg.name == "numpy":
        return 0
    else:
        return 1


def print_with_progress_line(str, progress_line):
    if not sys.stdout.isatty():
        print(str)
        return
    twidth = os.get_terminal_size()[0]
    print(" " * twidth, end="\r")
    print(str)
    if progress_line:
        print(progress_line, end="\r")


def get_progress_line(package_set):
    if not package_set:
        return None
    return f"In progress: " + ", ".join(package_set.keys())


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
    checks if any of the dependents are ready to be built. If so, it adds the
    package to the build queue.
    """

    # Insert packages into build_queue. We *must* do this after counting
    # dependents, because the ordering ought not to change after insertion.
    build_queue: PriorityQueue = PriorityQueue()

    print("Building the following packages: " + ", ".join(sorted(pkg_map.keys())))
    t0 = perf_counter()
    for pkg in pkg_map.values():
        if len(pkg.dependencies) == 0:
            build_queue.put((job_priority(pkg), pkg))

    built_queue: Queue = Queue()
    thread_lock = Lock()
    queue_idx = 1
    package_set = {}

    def builder(n):
        nonlocal queue_idx
        while True:
            pkg = build_queue.get()[1]
            with thread_lock:
                pkg._queue_idx = queue_idx
                queue_idx += 1
            package_set[pkg.name] = None
            msg = f"[{pkg._queue_idx}/{len(pkg_map)}] (thread {n}) building {pkg.name}"
            print_with_progress_line(msg, get_progress_line(package_set))
            t0 = perf_counter()
            success = True
            try:
                pkg.build(outputdir, args)
            except Exception as e:
                built_queue.put(e)
                success = False
                return
            finally:
                del package_set[pkg.name]
                status = "built" if success else "failed"
                msg = (
                    f"[{pkg._queue_idx}/{len(pkg_map)}] (thread {n}) "
                    f"{status} {pkg.name} in {perf_counter() - t0:.2f} s"
                )
                print_with_progress_line(msg, get_progress_line(package_set))
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
                build_queue.put((job_priority(dependent), dependent))

    for name in list(pkg_map):
        if (outputdir / (name + "-tests.js")).exists():
            pkg_map[name].unvendored_tests = True

    print(
        "\n===================================================\n"
        f"built all packages in {perf_counter() - t0:.2f} s"
    )


def generate_packages_json(pkg_map: Dict[str, BasePackage]) -> Dict:
    """Generate the package.json file"""
    # Build package.json data.
    package_data: Dict[str, Dict[str, Any]] = {
        "info": {"arch": "wasm32", "platform": "Emscripten-1.0"},
        "packages": {},
    }

    libraries = [pkg.name for pkg in pkg_map.values() if pkg.library]

    # unvendored stdlib modules
    for name in UNVENDORED_STDLIB_MODULES:
        pkg_entry: Dict[str, Any] = {
            "name": name,
            "version": "1.0",
            "depends": [],
            "imports": [name],
        }
        package_data["packages"][name.lower()] = pkg_entry

    for name, pkg in pkg_map.items():
        if pkg.library:
            continue
        pkg_entry = {"name": name, "version": pkg.version}
        if pkg.shared_library:
            pkg_entry["shared_library"] = True
        pkg_entry["depends"] = [
            x.lower() for x in pkg.dependencies if x not in libraries
        ]
        pkg_entry["imports"] = pkg.meta.get("test", {}).get("imports", [name])

        package_data["packages"][name.lower()] = pkg_entry

        if pkg.unvendored_tests:
            package_data["packages"][name.lower()]["unvendored_tests"] = True

            # Create the test package if necessary
            pkg_entry = {
                "name": name + "-tests",
                "version": pkg.version,
                "depends": [name.lower()],
                "imports": [],
            }
            package_data["packages"][name.lower() + "-tests"] = pkg_entry

    # Workaround for circular dependency between soupsieve and beautifulsoup4
    # TODO: FIXME!!
    if "soupsieve" in package_data["packages"]:
        package_data["packages"]["soupsieve"]["depends"].append("beautifulsoup4")

    # re-order packages by name
    package_data["packages"] = dict(sorted(package_data["packages"].items()))

    return package_data


def build_packages(packages_dir: Path, outputdir: Path, args) -> None:
    packages = common._parse_package_subset(args.only)

    pkg_map = generate_dependency_graph(packages_dir, packages)

    build_from_graph(pkg_map, outputdir, args)

    package_data = generate_packages_json(pkg_map)

    with open(outputdir / "packages.json", "w") as fd:
        json.dump(package_data, fd)


def make_parser(parser):
    parser.description = (
        "Build all the packages in a given directory\n\n"
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
        default=None,
        help="Extra compiling flags. Default: SIDE_MODULE_CFLAGS",
    )
    parser.add_argument(
        "--cxxflags",
        type=str,
        nargs="?",
        default=None,
        help=("Extra C++ specific compiling flags. " "Default: SIDE_MODULE_CXXFLAGS"),
    )
    parser.add_argument(
        "--ldflags",
        type=str,
        nargs="?",
        default=None,
        help="Extra linking flags. Default: SIDE_MODULE_LDFLAGS",
    )
    parser.add_argument(
        "--target-install-dir",
        type=str,
        nargs="?",
        default=None,
        help="The path to the target Python installation. Default: TARGETINSTALLDIR",
    )
    parser.add_argument(
        "--host-install-dir",
        type=str,
        nargs="?",
        default=None,
        help=("Directory for installing built host packages. Default: HOSTINSTALLDIR"),
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        dest="log_dir",
        nargs="?",
        default=None,
        help=("Directory to place log files"),
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
    if args.cflags is None:
        args.cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")
    if args.cxxflags is None:
        args.cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")
    if args.ldflags is None:
        args.ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")
    if args.target_install_dir is None:
        args.target_install_dir = common.get_make_flag("TARGETINSTALLDIR")
    if args.host_install_dir is None:
        args.host_install_dir = common.get_make_flag("HOSTINSTALLDIR")
    build_packages(packages_dir, outputdir, args)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
