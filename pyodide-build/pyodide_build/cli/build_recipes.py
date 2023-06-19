from pathlib import Path

import typer

from .. import build_env, buildall, buildpkg, pywasmcross
from ..build_env import init_environment
from ..common import get_num_cores
from ..logger import logger


def recipe(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or * for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is `./packages`",
    ),
    no_deps: bool = typer.Option(
        False, help="If true, do not build dependencies of the specified packages. "
    ),
    install: bool = typer.Option(
        False,
        help="If true, install the built packages into the install_dir. "
        "If false, build packages without installing.",
    ),
    install_dir: str = typer.Option(
        None,
        help="Path to install built packages and pyodide-lock.json. "
        "If not specified, the default is `./dist`.",
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
    continue_: bool = typer.Option(
        False,
        "--continue",
        help="Continue a build from the middle. For debugging. Implies '--force-rebuild'",
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
    """Build packages using yaml recipes and create pyodide-lock.json"""
    init_environment()

    if build_env.in_xbuildenv():
        build_env.check_emscripten_version()

    root = Path.cwd()
    recipe_dir_ = root / "packages" if not recipe_dir else Path(recipe_dir).resolve()
    install_dir_ = root / "dist" if not install_dir else Path(install_dir).resolve()
    log_dir_ = None if not log_dir else Path(log_dir).resolve()
    n_jobs = n_jobs or get_num_cores()

    if not recipe_dir_.is_dir():
        raise FileNotFoundError(f"Recipe directory {recipe_dir_} not found")

    build_args = pywasmcross.BuildArgs(
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )
    build_args = buildall.set_default_build_args(build_args)

    if no_deps:
        if install or log_dir_:
            logger.warning(
                "WARNING: when --no-deps is set, --install and --log-dir parameters are ignored",
            )

        # TODO: use multiprocessing?
        for package in packages:
            package_path = recipe_dir_ / package
            buildpkg.build_package(package_path, build_args, force_rebuild, continue_)

    else:
        if len(packages) == 1 and "," in packages[0]:
            # Handle packages passed with old comma separated syntax.
            # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
            targets = packages[0].replace(" ", "")
        else:
            targets = ",".join(packages)

        pkg_map = buildall.build_packages(
            recipe_dir_, targets, build_args, n_jobs, force_rebuild
        )

        if log_dir_:
            buildall.copy_logs(pkg_map, log_dir_)

        if install:
            buildall.install_packages(
                pkg_map, install_dir_, compression_level=compression_level
            )
