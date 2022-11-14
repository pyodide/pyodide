#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from functools import total_ordering
from graphlib import TopologicalSorter
from pathlib import Path
from queue import PriorityQueue, Queue
from threading import Lock, Thread
from time import perf_counter, sleep
from typing import Any

from . import common
from .buildpkg import needs_rebuild
from .common import find_matching_wheels
from .io import MetaConfig, _BuildSpecTypes


class BuildError(Exception):
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        super().__init__()


@total_ordering
@dataclasses.dataclass(eq=False, repr=False)
class BasePackage:
    pkgdir: Path
    name: str
    version: str
    disabled: bool
    meta: MetaConfig
    package_type: _BuildSpecTypes
    run_dependencies: list[str]
    host_dependencies: list[str]
    dependencies: set[str]  # run + host dependencies
    unbuilt_host_dependencies: set[str]
    host_dependents: set[str]
    unvendored_tests: Path | None = None
    file_name: str | None = None
    install_dir: str = "site"
    _queue_idx: int | None = None

    # We use this in the priority queue, which pops off the smallest element.
    # So we want the smallest element to have the largest number of dependents
    def __lt__(self, other: Any) -> bool:
        return len(self.host_dependents) > len(other.host_dependents)

    def __eq__(self, other: Any) -> bool:
        return len(self.host_dependents) == len(other.host_dependents)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name})"

    def needs_rebuild(self) -> bool:
        return needs_rebuild(self.pkgdir, self.pkgdir / "build", self.meta.source)

    def build(self, outputdir: Path, args: Any) -> None:
        raise NotImplementedError()

    def dist_artifact_path(self) -> Path:
        raise NotImplementedError()

    def tests_path(self) -> Path | None:
        return None


@dataclasses.dataclass
class Package(BasePackage):
    def __init__(self, pkgdir: Path):
        self.pkgdir = pkgdir

        pkgpath = pkgdir / "meta.yaml"
        if not pkgpath.is_file():
            raise ValueError(f"Directory {pkgdir} does not contain meta.yaml")

        self.meta = MetaConfig.from_yaml(pkgpath)
        self.name = self.meta.package.name
        self.version = self.meta.package.version
        self.disabled = self.meta.package.disabled
        self.package_type = self.meta.build.package_type

        assert self.name == pkgdir.name, f"{self.name} != {pkgdir.name}"

        self.run_dependencies = self.meta.requirements.run
        self.host_dependencies = self.meta.requirements.host
        self.dependencies = set(self.run_dependencies + self.host_dependencies)
        self.unbuilt_host_dependencies = set(self.host_dependencies)
        self.host_dependents = set()

    def dist_artifact_path(self) -> Path:
        dist_dir = self.pkgdir / "dist"
        if self.package_type in ("shared_library", "cpython_module"):
            candidates = list(dist_dir.glob("*.zip"))
        else:
            candidates = list(find_matching_wheels(dist_dir.glob("*.whl")))

        if len(candidates) != 1:
            raise RuntimeError(
                f"Unexpected number of wheels/archives {len(candidates)} when building {self.name}"
            )

        return candidates[0]

    def tests_path(self) -> Path | None:
        tests = list((self.pkgdir / "dist").glob("*-tests.tar"))
        assert len(tests) <= 1
        if tests:
            return tests[0]
        return None

    def build(self, outputdir: Path, args: Any) -> None:

        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pyodide_build",
                "buildpkg",
                str(self.pkgdir / "meta.yaml"),
                f"--cflags={args.cflags}",
                f"--cxxflags={args.cxxflags}",
                f"--ldflags={args.ldflags}",
                f"--target-install-dir={args.target_install_dir}",
                f"--host-install-dir={args.host_install_dir}",
                # Either this package has been updated and this doesn't
                # matter, or this package is dependent on a package that has
                # been updated and should be rebuilt even though its own
                # files haven't been updated.
                "--force-rebuild",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        log_dir = Path(args.log_dir).resolve() if args.log_dir else None
        if log_dir and (self.pkgdir / "build.log").exists():
            log_dir.mkdir(exist_ok=True, parents=True)
            shutil.copy(
                self.pkgdir / "build.log",
                log_dir / f"{self.name}.log",
            )

        if p.returncode != 0:
            print(f"Error building {self.name}. Printing build logs.")

            with open(self.pkgdir / "build.log") as f:
                shutil.copyfileobj(f, sys.stdout)

            print("ERROR: cancelling buildall")
            raise BuildError(p.returncode)


def validate_dependencies(pkg_map: dict[str, BasePackage]) -> None:
    for pkg_name, pkg in pkg_map.items():
        for runtime_dep_name in pkg.run_dependencies:
            runtime_dep = pkg_map[runtime_dep_name]
            if runtime_dep.package_type == "static_library":
                raise ValueError(
                    f"{pkg_name} has an invalid dependency: {runtime_dep_name}. Static libraries must be a host dependency."
                )


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
    pkg: BasePackage
    pkgname: str
    pkg_map: dict[str, BasePackage] = {}

    if "*" in packages:
        packages.discard("*")
        packages.update(
            str(x.name) for x in packages_dir.iterdir() if (x / "meta.yaml").is_file()
        )

    no_numpy_dependents = "no-numpy-dependents" in packages
    if no_numpy_dependents:
        packages.discard("no-numpy-dependents")

    disabled_packages = set()
    for pkgname in list(packages):
        if pkgname.startswith("!"):
            packages.discard(pkgname)
            disabled_packages.add(pkgname[1:])

    # Record which packages were requested. We need this information because
    # some packages are reachable from the initial set but are only reachable
    # via a disabled dependency.
    # Example: scikit-learn needs joblib & scipy, scipy needs numpy but numpy disabled.
    # We don't want to build joblib.
    requested = set(packages)

    # Create dependency graph.
    # On first pass add all dependencies regardless of whether
    # disabled since it might happen because of a transitive dependency
    graph = {}
    while packages:
        pkgname = packages.pop()

        pkg = Package(packages_dir / pkgname)
        pkg_map[pkgname] = pkg
        graph[pkgname] = pkg.dependencies
        for dep in pkg.dependencies:
            if pkg_map.get(dep) is None:
                packages.add(dep)

    validate_dependencies(pkg_map)

    # Traverse in build order (dependencies first then dependents)
    # Mark a package as disabled if they've either been explicitly disabled
    # or if any of its transitive dependencies were marked disabled.
    for pkgname in TopologicalSorter(graph).static_order():
        pkg = pkg_map[pkgname]
        if pkgname in disabled_packages:
            pkg.disabled = True
            continue
        if no_numpy_dependents and "numpy" in pkg.dependencies:
            pkg.disabled = True
            continue
        for dep in pkg.dependencies:
            if pkg_map[dep].disabled:
                pkg.disabled = True
                break

    # Now traverse in reverse build order (dependents first then their
    # dependencies).
    # Locate the subset of packages that are transitive dependencies of packages
    # that are requested and not disabled.
    for pkgname in reversed(list(TopologicalSorter(graph).static_order())):
        pkg = pkg_map[pkgname]
        if pkg.disabled:
            requested.discard(pkgname)
            continue

        if pkgname not in requested:
            continue

        requested.update(pkg.dependencies)
        for dep in pkg.host_dependencies:
            pkg_map[dep].host_dependents.add(pkg.name)

    return {name: pkg_map[name] for name in requested}


def job_priority(pkg: BasePackage) -> int:
    if pkg.name == "numpy":
        return 0
    else:
        return 1


def print_with_progress_line(str: str, progress_line: str | None) -> None:
    if not sys.stdout.isatty():
        print(str)
        return
    twidth = os.get_terminal_size()[0]
    print(" " * twidth, end="\r")
    print(str)
    if progress_line:
        print(progress_line, end="\r")


def get_progress_line(package_set: dict[str, None]) -> str | None:
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
) -> None:
    """
    Helper for generate_needs_build_set. Modifies needs_build in place.
    Recursively add pkg and all of its dependencies to needs_build.
    """
    if pkg.name in needs_build:
        return
    needs_build.add(pkg.name)
    for dep in pkg.host_dependents:
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


def build_from_graph(
    pkg_map: dict[str, BasePackage], outputdir: Path, args: argparse.Namespace
) -> None:
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
    build_queue: PriorityQueue[tuple[int, BasePackage]] = PriorityQueue()

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
        pkg_map[pkg_name].unbuilt_host_dependencies.difference_update(already_built)

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
        if len(pkg.unbuilt_host_dependencies) == 0:
            build_queue.put((job_priority(pkg), pkg))

    built_queue: Queue[BasePackage | Exception] = Queue()
    thread_lock = Lock()
    queue_idx = 1
    # Using dict keys for insertion order preservation
    package_set: dict[str, None] = {}

    def builder(n: int) -> None:
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
        match built_queue.get():
            case BuildError() as err:
                raise SystemExit(err.returncode)
            case Exception() as err:
                raise err
            case a_package:
                # MyPy should understand that this is a BasePackage
                assert not isinstance(a_package, Exception)
                pkg = a_package

        num_built += 1

        for _dependent in pkg.host_dependents:
            dependent = pkg_map[_dependent]
            dependent.unbuilt_host_dependencies.remove(pkg.name)
            if len(dependent.unbuilt_host_dependencies) == 0:
                build_queue.put((job_priority(dependent), dependent))

    print(
        "\n===================================================\n"
        f"built all packages in {perf_counter() - t0:.2f} s"
    )


def _generate_package_hash(full_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(full_path, "rb") as f:
        while chunk := f.read(4096):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_packagedata(
    output_dir: Path, pkg_map: dict[str, BasePackage]
) -> dict[str, Any]:
    packages: dict[str, Any] = {}
    for name, pkg in pkg_map.items():
        if not pkg.file_name or pkg.package_type == "static_library":
            continue
        if not Path(output_dir, pkg.file_name).exists():
            continue
        pkg_entry: Any = {
            "name": name,
            "version": pkg.version,
            "file_name": pkg.file_name,
            "install_dir": pkg.install_dir,
            "sha256": _generate_package_hash(Path(output_dir, pkg.file_name)),
        }

        pkg_type = pkg.package_type
        if pkg_type in ("shared_library", "cpython_module"):
            # We handle cpython modules as shared libraries
            pkg_entry["shared_library"] = True
            pkg_entry["install_dir"] = (
                "stdlib" if pkg_type == "cpython_module" else "dynlib"
            )

        pkg_entry["depends"] = [x.lower() for x in pkg.run_dependencies]
        pkg_entry["imports"] = (
            pkg.meta.package.top_level if pkg.meta.package.top_level else [name]
        )

        packages[name.lower()] = pkg_entry

        if pkg.unvendored_tests:
            packages[name.lower()]["unvendored_tests"] = True

            # Create the test package if necessary
            pkg_entry = {
                "name": name + "-tests",
                "version": pkg.version,
                "depends": [name.lower()],
                "imports": [],
                "file_name": pkg.unvendored_tests.name,
                "install_dir": pkg.install_dir,
                "sha256": _generate_package_hash(
                    Path(output_dir, pkg.unvendored_tests.name)
                ),
            }
            packages[name.lower() + "-tests"] = pkg_entry

    # sort packages by name
    packages = dict(sorted(packages.items()))
    return packages


def generate_repodata(
    output_dir: Path, pkg_map: dict[str, BasePackage]
) -> dict[str, dict[str, Any]]:
    """Generate the package.json file"""

    import sys

    sys.path.append(str(common.get_pyodide_root() / "src/py"))
    from pyodide import __version__

    # Build package.json data.
    [platform, _, arch] = common.platform().rpartition("_")
    info = {
        "arch": arch,
        "platform": platform,
        "version": __version__,
        "python": sys.version.partition(" ")[0],
    }
    packages = generate_packagedata(output_dir, pkg_map)
    return dict(info=info, packages=packages)


def copy_packages_to_dist_dir(
    packages: Iterable[BasePackage], output_dir: Path
) -> None:
    for pkg in packages:
        if pkg.package_type == "static_library":
            continue

        shutil.copy(pkg.dist_artifact_path(), output_dir)

        test_path = pkg.tests_path()
        if test_path:
            shutil.copy(test_path, output_dir)


def build_packages(
    packages_dir: Path, output_dir: Path, args: argparse.Namespace
) -> None:
    packages = common._parse_package_subset(args.only)

    pkg_map = generate_dependency_graph(packages_dir, packages)

    build_from_graph(pkg_map, output_dir, args)
    for pkg in pkg_map.values():
        assert isinstance(pkg, Package)

        if pkg.package_type == "static_library":
            continue

        pkg.file_name = pkg.dist_artifact_path().name
        pkg.unvendored_tests = pkg.tests_path()

    copy_packages_to_dist_dir(pkg_map.values(), output_dir)
    package_data = generate_repodata(output_dir, pkg_map)

    with open(output_dir / "repodata.json", "w") as fd:
        json.dump(package_data, fd)
        fd.write("\n")


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
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
        default="packages",
        help="Input directory containing a tree of package definitions",
    )
    parser.add_argument(
        "output",
        type=str,
        nargs=1,
        default="dist",
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


def main(args: argparse.Namespace) -> None:
    packages_dir = Path(args.dir[0]).resolve()
    outputdir = Path(args.output[0]).resolve()
    outputdir.mkdir(exist_ok=True)
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
