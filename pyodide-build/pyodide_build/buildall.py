#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import argparse
import dataclasses
import hashlib
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from functools import total_ordering
from graphlib import TopologicalSorter
from pathlib import Path
from queue import PriorityQueue, Queue
from threading import Lock, Thread
from time import perf_counter, sleep
from typing import Any

from rich.live import Live
from rich.progress import BarColumn, Progress, TimeElapsedColumn
from rich.spinner import Spinner
from rich.table import Table

from . import common, recipe
from .buildpkg import needs_rebuild
from .common import find_matching_wheels, find_missing_executables
from .io import MetaConfig, _BuildSpecTypes
from .logger import console_stdout, logger
from .pywasmcross import BuildArgs


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
    executables_required: list[str]
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

    def build(self, build_args: BuildArgs) -> None:
        raise NotImplementedError()

    def dist_artifact_path(self) -> Path:
        raise NotImplementedError()

    def tests_path(self) -> Path | None:
        return None


@dataclasses.dataclass
class Package(BasePackage):
    def __init__(self, pkgdir: Path, config: MetaConfig):
        self.pkgdir = pkgdir
        self.meta = config.copy(deep=True)

        self.name = self.meta.package.name
        self.version = self.meta.package.version
        self.disabled = self.meta.package.disabled
        self.package_type = self.meta.build.package_type

        assert self.name == pkgdir.name, f"{self.name} != {pkgdir.name}"

        self.run_dependencies = self.meta.requirements.run
        self.host_dependencies = self.meta.requirements.host
        self.executables_required = self.meta.requirements.executable
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

    def build(self, build_args: BuildArgs) -> None:

        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pyodide_build",
                "buildpkg",
                str(self.pkgdir / "meta.yaml"),
                f"--cflags={build_args.cflags}",
                f"--cxxflags={build_args.cxxflags}",
                f"--ldflags={build_args.ldflags}",
                f"--target-install-dir={build_args.target_install_dir}",
                f"--host-install-dir={build_args.host_install_dir}",
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

        if p.returncode != 0:
            logger.error(f"Error building {self.name}. Printing build logs.")
            logfile = self.pkgdir / "build.log"
            if logfile.is_file():
                logger.error(logfile.read_text(encoding="utf-8"))
            else:
                logger.error("ERROR: No build log found.")
            logger.error("ERROR: cancelling buildall")
            raise BuildError(p.returncode)


class PackageStatus:
    def __init__(
        self, *, name: str, idx: int, thread: int, total_packages: int
    ) -> None:
        self.pkg_name = name
        self.prefix = f"[{idx}/{total_packages}] " f"(thread {thread})"
        self.status = Spinner("dots", style="red", speed=0.2)
        self.table = Table.grid(padding=1)
        self.table.add_row(f"{self.prefix} building {self.pkg_name}", self.status)
        self.finished = False

    def finish(self, success: bool, elapsed_time: float) -> None:
        time = datetime.utcfromtimestamp(elapsed_time)
        if time.minute == 0:
            minutes = ""
        else:
            minutes = f"{time.minute}m "
        timestr = f"{minutes}{time.second}s"

        status = "built" if success else "failed"
        done_message = f"{self.prefix} {status} {self.pkg_name} in {timestr}"

        self.finished = True

        if success:
            logger.success(done_message)
        else:
            logger.error(done_message)

    def __rich__(self):
        return self.table


class ReplProgressFormatter:
    def __init__(self, num_packages: int) -> None:
        self.progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "{task.completed}/{task.total} [progress.percentage]{task.percentage:>3.0f}%",
            "Time elapsed:",
            TimeElapsedColumn(),
        )
        self.task = self.progress.add_task("Building packages...", total=num_packages)
        self.packages: list[PackageStatus] = []
        self.reset_grid()

    def reset_grid(self):
        """Empty out the rendered grids."""
        self.top_grid = Table.grid()

        for package in self.packages:
            self.top_grid.add_row(package)

        self.main_grid = Table.grid()
        self.main_grid.add_row(self.top_grid)
        self.main_grid.add_row(self.progress)

    def add_package(
        self, *, name: str, idx: int, thread: int, total_packages: int
    ) -> PackageStatus:
        status = PackageStatus(
            name=name, idx=idx, thread=thread, total_packages=total_packages
        )
        self.packages.append(status)
        self.reset_grid()
        return status

    def remove_package(self, pkg: PackageStatus) -> None:
        self.packages.remove(pkg)
        self.reset_grid()

    def update_progress_bar(self):
        """Step the progress bar by one (to show that a package finished)"""
        self.progress.update(self.task, advance=1)

    def __rich__(self):
        return self.main_grid


def _validate_package_map(pkg_map: dict[str, BasePackage]) -> bool:

    # Check if dependencies are valid
    for pkg_name, pkg in pkg_map.items():
        for runtime_dep_name in pkg.run_dependencies:
            runtime_dep = pkg_map[runtime_dep_name]
            if runtime_dep.package_type == "static_library":
                raise ValueError(
                    f"{pkg_name} has an invalid dependency: {runtime_dep_name}. Static libraries must be a host dependency."
                )

    # Check executables required to build packages are available
    missing_executables = defaultdict(list)
    for name, pkg in pkg_map.items():
        for exe in find_missing_executables(pkg.executables_required):
            missing_executables[exe].append(name)

    if missing_executables:
        error_msg = "The following executables are missing in the host system:\n"
        for executable, pkgs in missing_executables.items():
            error_msg += f"- {executable} (required by: {', '.join(pkgs)})\n"

        raise RuntimeError(error_msg)

    return True


def _parse_package_query(query: list[str] | str | None) -> tuple[set[str], set[str]]:
    """
    Parse a package query string into a list of requested packages and a list of
    disabled packages.

    Parameters
    ----------
    query
        A list of packages to build, this can be a comma separated string.

    Returns
    -------
    A tuple of two lists, the first list contains requested packages, the second
    list contains disabled packages.

    Examples
    --------
    >>> _parse_package_query(None)
    (set(), set())
    >>> requested, disabled = _parse_package_query("a,b,c")
    >>> requested == {'a', 'b', 'c'}, disabled == set()
    (True, True)
    >>> requested, disabled = _parse_package_query("a,b,!c")
    >>> requested == {'a', 'b'}, disabled == {'c'}
    (True, True)
    >>> requested, disabled = _parse_package_query(["a", "b", "!c"])
    >>> requested == {'a', 'b'}, disabled == {'c'}
    (True, True)
    """
    if not query:
        query = []

    if isinstance(query, str):
        query = [el.strip() for el in query.split(",")]

    requested = set()
    disabled = set()

    for name in query:
        if not name:  # empty string
            continue

        if name.startswith("!"):
            disabled.add(name[1:])
        else:
            requested.add(name)

    return requested, disabled


def generate_dependency_graph(
    packages_dir: Path,
    requested: set[str],
    disabled: set[str] | None = None,
) -> dict[str, BasePackage]:
    """This generates a dependency graph for given packages.

    A node in the graph is a BasePackage object defined above, which maintains
    a list of dependencies and also dependents. That is, each node stores both
    incoming and outgoing edges.

    The dependencies and dependents are stored via their name, and we have a
    lookup table pkg_map: Dict[str, BasePackage] to look up the corresponding
    BasePackage object. The function returns pkg_map, which contains all
    packages in the graph as its values.

    Parameters
    ----------
    packages_dir
        A directory that contains packages
    requested
        A set of packages to build
    disabled
        A set of packages to not build

    Returns
    -------
    A dictionary mapping package names to BasePackage objects
    """

    pkg: BasePackage
    pkgname: str
    pkg_map: dict[str, BasePackage] = {}

    if not disabled:
        disabled = set()

    # Create dependency graph.
    # On first pass add all dependencies regardless of whether
    # disabled since it might happen because of a transitive dependency
    graph = {}
    all_recipes = recipe.load_all_recipes(packages_dir)
    no_numpy_dependents = "no-numpy-dependents" in requested
    requested.discard("no-numpy-dependents")
    packages = requested.copy()

    while packages:
        pkgname = packages.pop()

        pkg = Package(packages_dir / pkgname, all_recipes[pkgname])
        pkg_map[pkgname] = pkg
        graph[pkgname] = pkg.dependencies
        for dep in pkg.dependencies:
            if pkg_map.get(dep) is None:
                packages.add(dep)

    # Traverse in build order (dependencies first then dependents)
    # Mark a package as disabled if they've either been explicitly disabled
    # or if any of its transitive dependencies were marked disabled.
    for pkgname in TopologicalSorter(graph).static_order():
        pkg = pkg_map[pkgname]
        if pkgname in disabled:
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
    requested_with_deps = requested.copy()
    for pkgname in reversed(list(TopologicalSorter(graph).static_order())):
        pkg = pkg_map[pkgname]
        if pkg.disabled:
            requested_with_deps.discard(pkgname)
            continue

        if pkgname not in requested_with_deps:
            continue

        requested_with_deps.update(pkg.dependencies)
        for dep in pkg.host_dependencies:
            pkg_map[dep].host_dependents.add(pkg.name)

    pkg_map = {name: pkg_map[name] for name in requested_with_deps}

    _validate_package_map(pkg_map)

    return pkg_map


def job_priority(pkg: BasePackage) -> int:
    if pkg.name == "numpy":
        return 0
    else:
        return 1


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
    pkg_map: dict[str, BasePackage],
    build_args: BuildArgs,
    n_jobs: int = 1,
    force_rebuild: bool = False,
) -> None:
    """
    This builds packages in pkg_map in parallel, building at most n_jobs
    packages at once.

    We have a priority queue of packages we are ready to build (build_queue),
    where a package is ready to build if all its dependencies are built. The
    priority is based on the number of dependents --- we prefer to build
    packages with more dependents first.

    To build packages in parallel, we use a thread pool of n_jobs many
    threads listening to build_queue. When the thread is free, it takes an
    item off build_queue and builds it. Once the package is built, it sends the
    package to the built_queue. The main thread listens to the built_queue and
    checks if any of the dependents are ready to be built. If so, it adds the
    package to the build queue.
    """

    # Insert packages into build_queue. We *must* do this after counting
    # dependents, because the ordering ought not to change after insertion.
    build_queue: PriorityQueue[tuple[int, BasePackage]] = PriorityQueue()

    if force_rebuild:
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
        logger.info(
            "The following packages are already built: "
            f"[bold]{format_name_list(sorted(already_built))}[/bold]"
        )
    if not needs_build:
        logger.success("All packages already built. Quitting.")
        return

    logger.info(
        "Building the following packages: "
        f"[bold]{format_name_list(sorted(needs_build))}[/bold]"
    )

    for pkg_name in needs_build:
        pkg = pkg_map[pkg_name]
        if len(pkg.unbuilt_host_dependencies) == 0:
            build_queue.put((job_priority(pkg), pkg))

    built_queue: Queue[BasePackage | Exception] = Queue()
    thread_lock = Lock()
    queue_idx = 1
    progress_formatter = ReplProgressFormatter(len(needs_build))

    def builder(n: int) -> None:
        nonlocal queue_idx
        while True:
            pkg = build_queue.get()[1]

            with thread_lock:
                pkg._queue_idx = queue_idx
                queue_idx += 1

            pkg_status = progress_formatter.add_package(
                name=pkg.name,
                idx=pkg._queue_idx,
                thread=n,
                total_packages=len(needs_build),
            )
            t0 = perf_counter()

            success = True
            try:
                pkg.build(build_args)
            except Exception as e:
                built_queue.put(e)
                success = False
                return
            finally:
                pkg_status.finish(success, perf_counter() - t0)
                progress_formatter.remove_package(pkg_status)

            built_queue.put(pkg)
            # Release the GIL so new packages get queued
            sleep(0.01)

    for n in range(0, n_jobs):
        Thread(target=builder, args=(n + 1,), daemon=True).start()

    num_built = len(already_built)
    with Live(progress_formatter, console=console_stdout):
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

            progress_formatter.update_progress_bar()

            for _dependent in pkg.host_dependents:
                dependent = pkg_map[_dependent]
                dependent.unbuilt_host_dependencies.remove(pkg.name)
                if len(dependent.unbuilt_host_dependencies) == 0:
                    build_queue.put((job_priority(dependent), dependent))


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
            "imports": [],
        }

        pkg_type = pkg.package_type
        if pkg_type in ("shared_library", "cpython_module"):
            # We handle cpython modules as shared libraries
            pkg_entry["shared_library"] = True
            pkg_entry["install_dir"] = (
                "stdlib" if pkg_type == "cpython_module" else "dynlib"
            )

        pkg_entry["depends"] = [x.lower() for x in pkg.run_dependencies]

        if pkg.package_type not in ("static_library", "shared_library"):
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
    packages_dir: Path,
    targets: str,
    build_args: BuildArgs,
    n_jobs: int = 1,
    force_rebuild: bool = False,
) -> dict[str, BasePackage]:
    requested, disabled = _parse_package_query(targets)
    requested_packages = recipe.load_recipes(packages_dir, requested)
    pkg_map = generate_dependency_graph(
        packages_dir, set(requested_packages.keys()), disabled
    )

    build_from_graph(pkg_map, build_args, n_jobs, force_rebuild)
    for pkg in pkg_map.values():
        assert isinstance(pkg, Package)

        if pkg.package_type == "static_library":
            continue

        pkg.file_name = pkg.dist_artifact_path().name
        pkg.unvendored_tests = pkg.tests_path()

    return pkg_map


def copy_logs(pkg_map: dict[str, BasePackage], log_dir: Path) -> None:
    """
    Copy build logs of packages to the log directory.
    Parameters
    ----------
    pkg_map
        A dictionary mapping package names to package objects.
    log_dir
        The directory to copy the logs to.
    """

    log_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Copying build logs to {log_dir}")

    for pkg in pkg_map.values():
        log_file = pkg.pkgdir / "build.log"
        if log_file.exists():
            shutil.copy(log_file, log_dir / f"{pkg.name}.log")
        else:
            logger.warning(f"Warning: {pkg.name} has no build log")


def install_packages(pkg_map: dict[str, BasePackage], output_dir: Path) -> None:
    """
    Install packages into the output directory.
    - copies build artifacts (wheel, zip, ...) to the output directory
    - create repodata.json


    pkg_map
        package map created from build_packages

    output_dir
        output directory to install packages into
    """

    output_dir.mkdir(exist_ok=True, parents=True)

    logger.info(f"Copying built packages to {output_dir}")
    copy_packages_to_dist_dir(pkg_map.values(), output_dir)

    repodata_path = output_dir / "repodata.json"
    logger.info(f"Writing repodata.json to {repodata_path}")

    package_data = generate_repodata(output_dir, pkg_map)
    with repodata_path.open("w") as fd:
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


def set_default_build_args(build_args: BuildArgs) -> BuildArgs:
    args = dataclasses.replace(build_args)

    if args.cflags is None:
        args.cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")  # type: ignore[unreachable]
    if args.cxxflags is None:
        args.cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")  # type: ignore[unreachable]
    if args.ldflags is None:
        args.ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")  # type: ignore[unreachable]
    if args.target_install_dir is None:
        args.target_install_dir = common.get_make_flag("TARGETINSTALLDIR")  # type: ignore[unreachable]
    if args.host_install_dir is None:
        args.host_install_dir = common.get_make_flag("HOSTINSTALLDIR")  # type: ignore[unreachable]

    return args


def main(args: argparse.Namespace) -> None:
    packages_dir = Path(args.dir[0]).resolve()
    outputdir = Path(args.output[0]).resolve()
    targets = args.only
    n_jobs = args.n_jobs
    log_dir = Path(args.log_dir) if args.log_dir else None
    force_rebuild = args.force_rebuild

    build_args = BuildArgs(
        pkgname="",
        cflags=args.cflags,
        cxxflags=args.cxxflags,
        ldflags=args.ldflags,
        target_install_dir=args.target_install_dir,
        host_install_dir=args.host_install_dir,
    )

    build_args = set_default_build_args(build_args)

    pkg_map = build_packages(
        packages_dir,
        targets,
        build_args=build_args,
        n_jobs=n_jobs,
        force_rebuild=force_rebuild,
    )

    if log_dir:
        copy_logs(pkg_map, log_dir)

    install_packages(pkg_map, outputdir)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
