#!/usr/bin/env python3

"""
Build all of the packages in a given directory.
"""

import dataclasses
import shutil
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import total_ordering
from graphlib import TopologicalSorter
from pathlib import Path
from queue import PriorityQueue, Queue
from threading import Lock, Thread
from time import perf_counter, sleep
from typing import Any

from packaging.utils import canonicalize_name
from pyodide_lock import PyodideLockSpec
from pyodide_lock.spec import PackageSpec as PackageLockSpec
from pyodide_lock.utils import update_package_sha256
from rich.live import Live
from rich.progress import BarColumn, Progress, TimeElapsedColumn
from rich.spinner import Spinner
from rich.table import Table

from . import build_env, recipe
from .build_env import BuildArgs
from .buildpkg import needs_rebuild
from .common import (
    extract_wheel_metadata_file,
    find_matching_wheels,
    find_missing_executables,
    repack_zip_archive,
)
from .io import MetaConfig, _BuildSpecTypes
from .logger import console_stdout, logger


class BuildError(Exception):
    def __init__(self, returncode: int, msg: str) -> None:
        self.returncode = returncode
        self.msg = msg
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

    def build_path(self, build_dir: Path) -> Path:
        return build_dir / self.name / "build"

    def needs_rebuild(self, build_dir: Path) -> bool:
        return needs_rebuild(self.pkgdir, self.build_path(build_dir), self.meta.source)

    def build(self, build_args: BuildArgs, build_dir: Path) -> None:
        raise NotImplementedError()

    def dist_artifact_path(self) -> Path:
        raise NotImplementedError()

    def tests_path(self) -> Path | None:
        return None


@dataclasses.dataclass
class Package(BasePackage):
    def __init__(self, pkgdir: Path, config: MetaConfig):
        self.pkgdir = pkgdir
        self.meta = config.model_copy(deep=True)

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
        if self.package_type == "shared_library":
            candidates = list(dist_dir.glob("*.zip"))
        else:
            candidates = list(
                find_matching_wheels(dist_dir.glob("*.whl"), build_env.pyodide_tags())
            )

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

    def build(self, build_args: BuildArgs, build_dir: Path) -> None:
        p = subprocess.run(
            [
                "pyodide",
                "build-recipes-no-deps",
                self.name,
                "--recipe-dir",
                str(self.pkgdir.parent),
                f"--cflags={build_args.cflags}",
                f"--cxxflags={build_args.cxxflags}",
                f"--ldflags={build_args.ldflags}",
                f"--target-install-dir={build_args.target_install_dir}",
                f"--host-install-dir={build_args.host_install_dir}",
                f"--build-dir={build_dir}",
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
            msg = []
            msg.append(f"Error building {self.name}. Printing build logs.")
            logfile = self.pkgdir / "build.log"
            if logfile.is_file():
                msg.append(logfile.read_text(encoding="utf-8") + "\n")
            else:
                msg.append("ERROR: No build log found.")
            msg.append(f"ERROR: cancelling buildall due to error building {self.name}")
            raise BuildError(p.returncode, "\n".join(msg))


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

        if pkgname not in all_recipes:
            raise ValueError(
                f"No metadata file found for the following package: {pkgname}"
            )

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
    disabled_packages = set()
    for pkgname in reversed(list(TopologicalSorter(graph).static_order())):
        pkg = pkg_map[pkgname]
        if pkg.disabled:
            requested_with_deps.discard(pkgname)
            disabled_packages.add(pkgname)
            continue

        if pkgname not in requested_with_deps:
            continue

        requested_with_deps.update(pkg.dependencies)
        for dep in pkg.host_dependencies:
            pkg_map[dep].host_dependents.add(pkg.name)

    pkg_map = {name: pkg_map[name] for name in requested_with_deps}

    _validate_package_map(pkg_map)

    if disabled_packages:
        logger.warning(
            f"The following packages are disabled: {', '.join(disabled_packages)}"
        )

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


def generate_needs_build_set(
    pkg_map: dict[str, BasePackage], build_dir: Path
) -> set[str]:
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
        if pkg.needs_rebuild(build_dir):
            mark_package_needs_build(pkg_map, pkg, needs_build)
    return needs_build


class _GraphBuilder:
    """A class to manage state for build_from_graph.

    build_from_graph has a bunch of moving parts: a threadpool, a Rich Live
    session to display progress information to the terminal, and a job graph to
    keep track of. This class keeps track of all this state.

    The only public class is `run`.
    """

    def __init__(
        self,
        pkg_map: dict[str, BasePackage],
        build_args: BuildArgs,
        build_dir: Path,
        needs_build: set[str],
    ):
        self.pkg_map: dict[str, BasePackage] = pkg_map
        self.build_args: BuildArgs = build_args
        self.build_dir: Path = build_dir
        self.needs_build: set[str] = needs_build
        self.build_queue: PriorityQueue[tuple[int, BasePackage]] = PriorityQueue()
        self.built_queue: Queue[tuple[BasePackage, BaseException | None]] = Queue()
        self.lock: Lock = Lock()
        self.building_rust_pkg: bool = False
        self.queue_idx: int = 1
        self.progress_formatter: ReplProgressFormatter = ReplProgressFormatter(
            len(self.needs_build)
        )

    @contextmanager
    def _queue_index(self, pkg: BasePackage) -> Iterator[int | None]:
        """
        yield the queue_index for the current job or None if the job is a Rust
        job and the rust lock is currently held.

        Set up as a context manager just for the rust packages.
        """
        is_rust_pkg = pkg.meta.is_rust_package()
        with self.lock:
            queue_idx = self.queue_idx
            if is_rust_pkg and self.building_rust_pkg:
                # Don't build multiple rust packages at the same time.
                # See: https://github.com/pyodide/pyodide/issues/3565
                # Note that if there are only rust packages left in the queue,
                # this will keep pushing and popping packages until the current rust package
                # is built. This is not ideal but presumably the overhead is negligible.
                self.build_queue.put((job_priority(pkg), pkg))
                yield None
                return
            if is_rust_pkg:
                self.building_rust_pkg = True
            self.queue_idx += 1
        try:
            yield queue_idx
        finally:
            if is_rust_pkg:
                self.building_rust_pkg = False

    @contextmanager
    def _pkg_status_display(self, n: int, pkg: BasePackage) -> Iterator[None]:
        """Control the status information for the package.

        Prints the "[{pkg-num}/{total_packages}] (thread n) building {package_name}"
        message and when done prints "succeeded/failed building package ... in ... seconds"
        plus updates the progress info in the console.
        """
        idx = pkg._queue_idx
        assert idx
        pkg_status = self.progress_formatter.add_package(
            name=pkg.name,
            idx=idx,
            thread=n,
            total_packages=len(self.needs_build),
        )
        t0 = perf_counter()
        success = True
        try:
            yield
        except BaseException:
            success = False
            raise
        finally:
            pkg_status.finish(success, perf_counter() - t0)
            self.progress_formatter.remove_package(pkg_status)

    def _build_one(self, n: int, pkg: BasePackage) -> BaseException | None:
        try:
            with self._pkg_status_display(n, pkg):
                pkg.build(self.build_args, self.build_dir)
        except BaseException as e:
            return e
        else:
            return None

    def _builder(self, n: int) -> None:
        """This is the logic that controls a thread in the thread pool."""
        while True:
            pkg = self.build_queue.get()[1]
            with self._queue_index(pkg) as idx:
                if idx is None:
                    # Rust package and we're already building one.
                    # Release the GIL so new packages get queued
                    sleep(0.01)
                    continue
                pkg._queue_idx = idx
                res = self._build_one(n, pkg)
                self.built_queue.put((pkg, res))
                if res:
                    # Build failed, quit the thread.
                    # Note that all other threads just keep going for a bit
                    # longer until we call sys.exit
                    return
                # Release the GIL so new packages get queued
                sleep(0.01)

    def run(self, n_jobs: int, already_built: set[str]) -> None:
        """Build the graph with n_jobs threads

        Prepare the queue by locating packages with no deps, set up the cli
        progress display, start up the threads, and manage build queue.
        """
        for pkg_name in self.needs_build:
            pkg = self.pkg_map[pkg_name]
            if len(pkg.unbuilt_host_dependencies) == 0:
                self.build_queue.put((job_priority(pkg), pkg))

        num_built = len(already_built)
        with Live(self.progress_formatter, console=console_stdout):
            for n in range(0, n_jobs):
                Thread(target=self._builder, args=(n + 1,), daemon=True).start()

            while num_built < len(self.pkg_map):
                [pkg, err] = self.built_queue.get()
                if err:
                    raise err

                num_built += 1

                self.progress_formatter.update_progress_bar()

                for _dependent in pkg.host_dependents:
                    dependent = self.pkg_map[_dependent]
                    dependent.unbuilt_host_dependencies.remove(pkg.name)
                    if len(dependent.unbuilt_host_dependencies) == 0:
                        self.build_queue.put((job_priority(dependent), dependent))


def build_from_graph(
    pkg_map: dict[str, BasePackage],
    build_args: BuildArgs,
    build_dir: Path,
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

    if force_rebuild:
        # If "force_rebuild" is set, just rebuild everything
        needs_build = set(pkg_map.keys())
    else:
        needs_build = generate_needs_build_set(pkg_map, build_dir)

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

    sorted_needs_build = sorted(needs_build)
    logger.info(
        "Building the following packages: "
        f"[bold]{format_name_list(sorted_needs_build)}[/bold]"
    )
    build_state = _GraphBuilder(pkg_map, build_args, build_dir, set(needs_build))
    try:
        build_state.run(n_jobs, already_built)
    except BuildError as err:
        logger.error(err.msg)
        sys.exit(err.returncode)


def generate_packagedata(
    output_dir: Path, pkg_map: dict[str, BasePackage]
) -> dict[str, PackageLockSpec]:
    packages: dict[str, PackageLockSpec] = {}
    for name, pkg in pkg_map.items():
        normalized_name = canonicalize_name(name)

        if not pkg.file_name or pkg.package_type == "static_library":
            continue
        if not Path(output_dir, pkg.file_name).exists():
            continue
        pkg_entry = PackageLockSpec(
            name=name,
            version=pkg.version,
            file_name=pkg.file_name,
            install_dir=pkg.install_dir,
            package_type=pkg.package_type,
        )

        update_package_sha256(pkg_entry, output_dir / pkg.file_name)

        pkg_type = pkg.package_type
        if pkg_type == "shared_library":
            # We handle cpython modules as shared libraries
            pkg_entry.shared_library = True
            pkg_entry.install_dir = "dynlib"

        pkg_entry.depends = [x.lower() for x in pkg.run_dependencies]

        if pkg.package_type not in ("static_library", "shared_library"):
            pkg_entry.imports = (
                pkg.meta.package.top_level if pkg.meta.package.top_level else [name]
            )

        packages[normalized_name.lower()] = pkg_entry

        if pkg.unvendored_tests:
            packages[normalized_name.lower()].unvendored_tests = True

            # Create the test package if necessary
            pkg_entry = PackageLockSpec(
                name=name + "-tests",
                version=pkg.version,
                depends=[name.lower()],
                file_name=pkg.unvendored_tests.name,
                install_dir=pkg.install_dir,
            )

            update_package_sha256(pkg_entry, output_dir / pkg.unvendored_tests.name)

            packages[normalized_name.lower() + "-tests"] = pkg_entry

    # sort packages by name
    packages = dict(sorted(packages.items()))
    return packages


def generate_lockfile(
    output_dir: Path, pkg_map: dict[str, BasePackage]
) -> PyodideLockSpec:
    """Generate the package.json file"""

    # Build package.json data.
    [platform, _, arch] = build_env.platform().rpartition("_")
    info = {
        "arch": arch,
        "platform": platform,
        "version": build_env.get_build_flag("PYODIDE_VERSION"),
        "python": sys.version.partition(" ")[0],
        "abi_version": build_env.get_build_flag("PYODIDE_ABI_VERSION"),
    }
    packages = generate_packagedata(output_dir, pkg_map)
    lock_spec = PyodideLockSpec(info=info, packages=packages)
    lock_spec.check_wheel_filenames()
    return lock_spec


def copy_packages_to_dist_dir(
    packages: Iterable[BasePackage],
    output_dir: Path,
    compression_level: int = 6,
    metadata_files: bool = False,
) -> None:
    for pkg in packages:
        if pkg.package_type == "static_library":
            continue

        dist_artifact_path = pkg.dist_artifact_path()

        shutil.copy(dist_artifact_path, output_dir)
        repack_zip_archive(
            output_dir / dist_artifact_path.name, compression_level=compression_level
        )

        if metadata_files and dist_artifact_path.suffix == ".whl":
            extract_wheel_metadata_file(
                dist_artifact_path,
                output_dir / f"{dist_artifact_path.name}.metadata",
            )

        test_path = pkg.tests_path()
        if test_path:
            shutil.copy(test_path, output_dir)


def build_packages(
    packages_dir: Path,
    targets: str,
    build_args: BuildArgs,
    build_dir: Path,
    n_jobs: int = 1,
    force_rebuild: bool = False,
) -> dict[str, BasePackage]:
    requested, disabled = _parse_package_query(targets)
    requested_packages = recipe.load_recipes(packages_dir, requested)
    pkg_map = generate_dependency_graph(
        packages_dir, set(requested_packages.keys()), disabled
    )

    build_from_graph(pkg_map, build_args, build_dir, n_jobs, force_rebuild)
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


def install_packages(
    pkg_map: dict[str, BasePackage],
    output_dir: Path,
    compression_level: int = 6,
    metadata_files: bool = False,
) -> None:
    """
    Install packages into the output directory.
    - copies build artifacts (wheel, zip, ...) to the output directory
    - create pyodide-lock.json


    pkg_map
        package map created from build_packages

    output_dir
        output directory to install packages into
    """

    output_dir.mkdir(exist_ok=True, parents=True)

    logger.info(f"Copying built packages to {output_dir}")
    copy_packages_to_dist_dir(
        pkg_map.values(),
        output_dir,
        compression_level=compression_level,
        metadata_files=metadata_files,
    )

    lockfile_path = output_dir / "pyodide-lock.json"
    logger.info(f"Writing pyodide-lock.json to {lockfile_path}")

    package_data = generate_lockfile(output_dir, pkg_map)
    package_data.to_json(lockfile_path)


def set_default_build_args(build_args: BuildArgs) -> BuildArgs:
    args = dataclasses.replace(build_args)

    if not args.cflags:
        args.cflags = build_env.get_build_flag("SIDE_MODULE_CFLAGS")
    if not args.cxxflags:
        args.cxxflags = build_env.get_build_flag("SIDE_MODULE_CXXFLAGS")
    if not args.ldflags:
        args.ldflags = build_env.get_build_flag("SIDE_MODULE_LDFLAGS")
    if not args.target_install_dir:
        args.target_install_dir = build_env.get_build_flag("TARGETINSTALLDIR")
    if not args.host_install_dir:
        args.host_install_dir = build_env.get_build_flag("HOSTINSTALLDIR")

    return args
