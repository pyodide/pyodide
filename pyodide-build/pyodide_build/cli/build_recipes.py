import dataclasses
import sys
from pathlib import Path

import typer

from .. import build_env, buildall, buildpkg
from ..build_env import init_environment
from ..common import get_num_cores
from ..logger import logger
from ..pywasmcross import BuildArgs


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class Args:
    recipe_dir: Path
    build_dir: Path
    install_dir: Path
    build_args: BuildArgs
    force_rebuild: bool
    n_jobs: int

    def __init__(
        self,
        *,
        recipe_dir: Path | str | None,
        build_dir: Path | str | None,
        install_dir: Path | str | None = None,
        build_args: BuildArgs,
        force_rebuild: bool,
        n_jobs: int | None = None,
    ):
        root = Path.cwd()
        self.recipe_dir = (
            root / "packages" if not recipe_dir else Path(recipe_dir).resolve()
        )
        self.build_dir = self.recipe_dir if not build_dir else Path(build_dir).resolve()
        self.install_dir = (
            root / "dist" if not install_dir else Path(install_dir).resolve()
        )
        self.build_args = build_args
        self.force_rebuild = force_rebuild
        self.n_jobs = n_jobs or get_num_cores()
        if not self.recipe_dir.is_dir():
            raise FileNotFoundError(f"Recipe directory {self.recipe_dir} not found")


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class InstallOptions:
    compression_level: int
    metadata_files: bool


def build_recipes_no_deps(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or ``*`` for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is ``./packages``",
    ),
    build_dir: str = typer.Option(
        None,
        envvar="PYODIDE_RECIPE_BUILD_DIR",
        help="The directory where build directories for packages are created. "
        "Default: recipe_dir.",
    ),
    cflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CFLAGS"
    ),
    cxxflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CXXFLAGS"
    ),
    ldflags: str = typer.Option(
        None, help="Extra linking flags. Default: SIDE_MODULE_LDFLAGS"
    ),
    target_install_dir: str = typer.Option(
        None,
        help="The path to the target Python installation. Default: TARGETINSTALLDIR",
    ),
    host_install_dir: str = typer.Option(
        None,
        help="Directory for installing built host packages. Default: HOSTINSTALLDIR",
    ),
    force_rebuild: bool = typer.Option(
        False,
        help="Force rebuild of all packages regardless of whether they appear to have been updated",
    ),
    continue_: bool = typer.Option(
        False,
        "--continue",
        help="Continue a build from the middle. For debugging. Implies '--force-rebuild'",
    ),
) -> None:
    """Build packages using yaml recipes but don't try to resolve dependencies"""
    init_environment()

    if build_env.in_xbuildenv():
        build_env.check_emscripten_version()

    build_args = BuildArgs(
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )
    build_args = buildall.set_default_build_args(build_args)
    args = Args(
        build_args=build_args,
        build_dir=build_dir,
        recipe_dir=recipe_dir,
        force_rebuild=force_rebuild,
    )

    return build_recipes_no_deps_impl(packages, args, continue_)


def build_recipes_no_deps_impl(
    packages: list[str], args: Args, continue_: bool
) -> None:
    # TODO: use multiprocessing?
    for package in packages:
        package_path = args.recipe_dir / package
        buildpkg.build_package(
            package_path, args.build_args, args.build_dir, args.force_rebuild, continue_
        )


def build_recipes(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or ``*`` for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is ``./packages``",
    ),
    build_dir: str = typer.Option(
        None,
        envvar="PYODIDE_RECIPE_BUILD_DIR",
        help="The directory where build directories for packages are created. "
        "Default: recipe_dir.",
    ),
    install: bool = typer.Option(
        False,
        help="If true, install the built packages into the install_dir. "
        "If false, build packages without installing.",
    ),
    install_dir: str = typer.Option(
        None,
        help="Path to install built packages and pyodide-lock.json. "
        "If not specified, the default is ``./dist``.",
    ),
    metadata_files: bool = typer.Option(
        False,
        help="If true, extract the METADATA file from the built wheels "
        "to a matching ``*.whl.metadata`` file. "
        "If false, no ``*.whl.metadata`` file is produced.",
    ),
    no_deps: bool = typer.Option(
        False, help="Removed, use `pyodide build-recipes-no-deps` instead."
    ),
    cflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CFLAGS"
    ),
    cxxflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CXXFLAGS"
    ),
    ldflags: str = typer.Option(
        None, help="Extra linking flags. Default: SIDE_MODULE_LDFLAGS"
    ),
    target_install_dir: str = typer.Option(
        None,
        help="The path to the target Python installation. Default: TARGETINSTALLDIR",
    ),
    host_install_dir: str = typer.Option(
        None,
        help="Directory for installing built host packages. Default: HOSTINSTALLDIR",
    ),
    log_dir: str = typer.Option(None, help="Directory to place log files"),
    force_rebuild: bool = typer.Option(
        False,
        help="Force rebuild of all packages regardless of whether they appear to have been updated",
    ),
    n_jobs: int = typer.Option(
        None,
        help="Number of packages to build in parallel  (default: # of cores in the system)",
    ),
    compression_level: int = typer.Option(
        6,
        help="Level of zip compression to apply when installing. 0 means no compression.",
    ),
) -> None:
    if no_deps:
        logger.error(
            "--no-deps has been removed, use pyodide build-package-no-deps instead",
        )
        sys.exit(1)
    if metadata_files and not install:
        logger.warning(
            "WARNING: when --install is not set, the --metadata-files parameter is ignored",
        )

    install_options: InstallOptions | None = None
    if install:
        install_options = InstallOptions(
            metadata_files=metadata_files, compression_level=compression_level
        )

    init_environment()

    if build_env.in_xbuildenv():
        build_env.check_emscripten_version()

    build_args = BuildArgs(
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )
    build_args = buildall.set_default_build_args(build_args)
    args = Args(
        build_args=build_args,
        build_dir=build_dir,
        install_dir=install_dir,
        recipe_dir=recipe_dir,
        force_rebuild=force_rebuild,
        n_jobs=n_jobs,
    )
    log_dir_ = Path(log_dir).resolve() if log_dir else None
    build_recipes_impl(packages, args, log_dir_, install_options)


def build_recipes_impl(
    packages: list[str],
    args: Args,
    log_dir: Path | None,
    install_options: InstallOptions | None,
) -> None:
    if len(packages) == 1 and "," in packages[0]:
        # Handle packages passed with old comma separated syntax.
        # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
        targets = packages[0].replace(" ", "")
    else:
        targets = ",".join(packages)

    pkg_map = buildall.build_packages(
        args.recipe_dir,
        targets=targets,
        build_args=args.build_args,
        build_dir=args.build_dir,
        n_jobs=args.n_jobs,
        force_rebuild=args.force_rebuild,
    )

    if log_dir:
        buildall.copy_logs(pkg_map, log_dir)

    if install_options:
        buildall.install_packages(
            pkg_map,
            args.install_dir,
            compression_level=install_options.compression_level,
            metadata_files=install_options.metadata_files,
        )
