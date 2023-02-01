from pathlib import Path

import typer

from .. import buildall, common, pywasmcross
from ..out_of_tree.utils import initialize_pyodide_root


def _get_num_cores() -> int:
    import multiprocessing

    return multiprocessing.cpu_count()


def recipe(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or * for all packages in recipe directory"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is `./packages`",
    ),
    install: bool = typer.Option(
        False,
        help="If true, install the built packages into the install_dir. "
        "If false, build packages without installing.",
    ),
    install_dir: str = typer.Option(
        None,
        help="Path to install built packages and repodata.json. "
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
    n_jobs: int = typer.Option(
        None,
        help="Number of packages to build in parallel  (default: # of cores in the system)",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Build packages using yaml recipes and create repodata.json"""
    initialize_pyodide_root()

    if common.in_xbuildenv():
        common.check_emscripten_version()

    root = Path.cwd()
    recipe_dir_ = root / "packages" if not recipe_dir else Path(recipe_dir).resolve()
    install_dir_ = root / "dist" if not install_dir else Path(install_dir).resolve()
    log_dir_ = None if not log_dir else Path(log_dir).resolve()
    n_jobs = n_jobs or _get_num_cores()

    build_args = pywasmcross.BuildArgs(
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        host_install_dir=host_install_dir,
    )

    if len(packages) == 1 and "," in packages[0]:
        # Handle packages passed with old comma separated syntax.
        # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
        targets = packages[0].replace(" ", "")
    else:
        targets = ",".join(packages)

    build_args = buildall.set_default_build_args(build_args)
    pkg_map = buildall.build_packages(
        recipe_dir_, targets, build_args, n_jobs, force_rebuild
    )

    if log_dir_:
        buildall.copy_logs(pkg_map, log_dir_)

    if install:
        buildall.install_packages(pkg_map, install_dir_)
