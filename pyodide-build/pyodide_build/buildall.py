#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from functools import total_ordering
from pathlib import Path
from queue import PriorityQueue, Queue
from threading import Lock, Thread
from time import perf_counter, sleep
from typing import Any, Optional

from . import common
from .buildpkg import needs_rebuild
from .common import UNVENDORED_STDLIB_MODULES, find_matching_wheels
from .io import parse_package_config


class BuildError(Exception):
    def __init__(self, returncode):
        self.returncode = returncode
        super().__init__()


class BasePackage:
    pkgdir: Path
    name: str
    version: str
    meta: dict
    library: bool
    shared_library: bool
    dependencies: list[str]
    unbuilt_dependencies: set[str]
    dependents: set[str]
    unvendored_tests: Optional[Path] = None
    file_name: Optional[str] = None
    install_dir: str = "site"

    # We use this in the priority queue, which pops off the smallest element.
    # So we want the smallest element to have the largest number of dependents
    def __lt__(self, other) -> bool:
        return len(self.dependents) > len(other.dependents)

    def __eq__(self, other) -> bool:
        return len(self.dependents) == len(other.dependents)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name})"

    def needs_rebuild(self) -> bool:
        return needs_rebuild(self.pkgdir, self.pkgdir / "build", self.meta)


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
        self.install_dir = "lib"

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
        self.meta["build"] = self.meta.get("build", {})
        self.meta["requirements"] = self.meta.get("requirements", {})

        self.library = self.meta["build"].get("library", False)
        self.shared_library = self.meta["build"].get("sharedlibrary", False)

        assert self.name == pkgdir.stem

        self.dependencies = self.meta["requirements"].get("run", [])
        self.unbuilt_dependencies = set(self.dependencies)
        self.dependents = set()

    def wheel_path(self) -> Path:
        dist_dir = self.pkgdir / "dist"
        wheel, *rest = find_matching_wheels(dist_dir.glob("*.whl"))
        if rest:
            raise Exception(
                f"Unexpected number of wheels {len(rest) + 1} when building {self.name}"
            )
        return wheel

    def tests_path(self) -> Optional[Path]:
        tests = list((self.pkgdir / "dist").glob("*-tests.tar"))
        assert len(tests) <= 1
        if tests:
            return tests[0]
        return None

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
                    # Either this package has been updated and this doesn't
                    # matter, or this package is dependent on a package that has
                    # been updated and should be rebuilt even though its own
                    # files haven't been updated.
                    "--force-rebuild",
                ],
                check=False,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        # Don't overwrite build log if we didn't build the file.
        # If the file didn't need to be rebuilt, the log will have exactly two lines.
        rebuilt = True
        with open(self.pkgdir / "build.log.tmp") as f:
            try:
                next(f)
                next(f)
                next(f)
            except StopIteration:
                rebuilt = False

        if rebuilt:
            shutil.move(self.pkgdir / "build.log.tmp", self.pkgdir / "build.log")
            log_dir = Path(args.log_dir).resolve() if args.log_dir else None

            if log_dir and (self.pkgdir / "build.log").exists():
                log_dir.mkdir(exist_ok=True, parents=True)
                shutil.copy(
                    self.pkgdir / "build.log",
                    log_dir / f"{self.name}.log",
                )
        else:
            (self.pkgdir / "build.log.tmp").unlink()

        if p.returncode != 0:
            print(f"Error building {self.name}. Printing build logs.")

            with open(self.pkgdir / "build.log") as f:
                shutil.copyfileobj(f, sys.stdout)

            print("ERROR: cancelling buildall")
            raise BuildError(p.returncode)

        if self.library:
            return
        if self.shared_library:
            file_path = Path(self.pkgdir / f"{self.name}-{self.version}.zip")
            shutil.copy(file_path, outputdir)
            file_path.unlink()
            return

        shutil.copy(self.wheel_path(), outputdir)
        test_path = self.tests_path()
        if test_path:
            shutil.copy(test_path, outputdir)


def generate_dependency_graph(
    packages_dir: Path, packages: set[str]
) -> dict[str, BasePackage]:
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

    pkg_map: dict[str, BasePackage] = {}

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
    return "In progress: " + ", ".join(package_set.keys())


def format_name_list(l: list[str]) -> str:
    """
    >>> format_name_list(["regex"])
    'regex'
    >>> format_name_list(["regex", "parso"])
    'regex and parso'
    >>> format_name_list(["regex", "parso", "jedi"])
    'regex, parso, and jedi'
    """
    if len(l) == 1:
        return l[0]
    most = l[:-1]
    if len(most) > 1:
        most = [x + "," for x in most]
    return " ".join(most) + " and " + l[-1]


def mark_package_needs_build(
    pkg_map: dict[str, BasePackage], pkg: BasePackage, needs_build: set[str]
):
    """
    Helper for generate_needs_build_set. Modifies needs_build in place.
    Recursively add pkg and all of its dependencies to needs_build.
    """
    if isinstance(pkg, StdLibPackage):
        return
    if pkg.name in needs_build:
        return
    needs_build.add(pkg.name)
    for dep in pkg.dependents:
        mark_package_needs_build(pkg_map, pkg_map[dep], needs_build)


def generate_needs_build_set(pkg_map: dict[str, BasePackage]) -> set[str]:
    """
    Generate the set of packages that need to be rebuilt.

    This consists of:
    1. packages whose source files have changed since they were last built
       according to needs_rebuild, and
    2. packages which depend on case 1 packages.
    """
    needs_build: set[str] = set()
    for pkg in pkg_map.values():
        # Otherwise, rebuild packages that have been updated and their dependents.
        if pkg.needs_rebuild():
            mark_package_needs_build(pkg_map, pkg, needs_build)
    return needs_build


def build_from_graph(pkg_map: dict[str, BasePackage], outputdir: Path, args) -> None:
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

    if args.force_rebuild:
        # If "force_rebuild" is set, just rebuild everything
        needs_build = set(pkg_map.keys())
    else:
        needs_build = generate_needs_build_set(pkg_map)

    # We won't rebuild the complement of the packages that we will build.
    already_built = set(pkg_map.keys()).difference(needs_build)

    # Remove the packages we've already built from the dependency sets of
    # the remaining ones
    for pkg_name in needs_build:
        pkg_map[pkg_name].unbuilt_dependencies.difference_update(already_built)

    if already_built:
        print(
            f"The following packages are already built: {format_name_list(sorted(already_built))}\n"
        )
    if not needs_build:
        print("All packages already built. Quitting.")
        return
    print(f"Building the following packages: {format_name_list(sorted(needs_build))}")

    t0 = perf_counter()
    for pkg_name in needs_build:
        pkg = pkg_map[pkg_name]
        if len(pkg.unbuilt_dependencies) == 0:
            build_queue.put((job_priority(pkg), pkg))

    built_queue: Queue = Queue()
    thread_lock = Lock()
    queue_idx = 1
    # Using dict keys for insertion order preservation
    package_set: dict[str, None] = {}

    def builder(n):
        nonlocal queue_idx
        while True:
            pkg = build_queue.get()[1]
            with thread_lock:
                pkg._queue_idx = queue_idx
                queue_idx += 1
            package_set[pkg.name] = None
            msg = f"[{pkg._queue_idx}/{len(needs_build)}] (thread {n}) building {pkg.name}"
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
                    f"[{pkg._queue_idx}/{len(needs_build)}] (thread {n}) "
                    f"{status} {pkg.name} in {perf_counter() - t0:.2f} s"
                )
                print_with_progress_line(msg, get_progress_line(package_set))
            built_queue.put(pkg)
            # Release the GIL so new packages get queued
            sleep(0.01)

    for n in range(0, args.n_jobs):
        Thread(target=builder, args=(n + 1,), daemon=True).start()

    num_built = len(already_built)
    while num_built < len(pkg_map):
        pkg = built_queue.get()
        if isinstance(pkg, BuildError):
            raise SystemExit(pkg.returncode)
        if isinstance(pkg, Exception):
            raise pkg

        num_built += 1

        for _dependent in pkg.dependents:
            dependent = pkg_map[_dependent]
            dependent.unbuilt_dependencies.remove(pkg.name)
            if len(dependent.unbuilt_dependencies) == 0:
                build_queue.put((job_priority(dependent), dependent))

    print(
        "\n===================================================\n"
        f"built all packages in {perf_counter() - t0:.2f} s"
    )


def generate_packages_json(pkg_map: dict[str, BasePackage]) -> dict:
    """Generate the package.json file"""
    # Build package.json data.
    package_data: dict[str, dict[str, Any]] = {
        "info": {"arch": "wasm32", "platform": "Emscripten-1.0"},
        "packages": {},
    }

    libraries = [pkg.name for pkg in pkg_map.values() if pkg.library]

    for name, pkg in pkg_map.items():
        if not pkg.file_name:
            continue
        pkg_entry: Any = {
            "name": name,
            "version": pkg.version,
            "file_name": pkg.file_name,
            "install_dir": pkg.install_dir,
        }
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
                "file_name": pkg.unvendored_tests.name,
                "install_dir": pkg.install_dir,
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
    for pkg in pkg_map.values():
        if pkg.library:
            continue
        if isinstance(pkg, StdLibPackage):
            pkg.file_name = pkg.name + ".tar"
            continue
        if pkg.needs_rebuild():
            continue
        if pkg.shared_library:
            pkg.file_name = f"{pkg.name}-{pkg.version}.zip"
            continue
        assert isinstance(pkg, Package)
        pkg.file_name = pkg.wheel_path().name
        pkg.unvendored_tests = pkg.tests_path()

    package_data = generate_packages_json(pkg_map)

    with open(outputdir / "packages.json", "w") as fd:
        json.dump(package_data, fd)
        fd.write("\n")


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
        "--force-rebuild",
        action="store_true",
        help=(
            "Force rebuild of all packages regardless of whether they appear to have been updated"
        ),
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
