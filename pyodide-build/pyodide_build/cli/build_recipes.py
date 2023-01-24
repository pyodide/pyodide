import argparse
from pathlib import Path

import typer

from .. import buildall

app = typer.Typer()


@app.command()  # type: ignore[misc]
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
    n_jobs: int = typer.Option(4, help="Number of packages to build in parallel"),
    ctx: typer.Context = typer.Context,
) -> None:
    """Build packages using yaml recipes and create repodata.json"""
    root = Path.cwd()
    recipe_dir_ = root / "packages" if not recipe_dir else Path(recipe_dir)
    install_dir_ = root / "dist" if not install_dir else Path(install_dir)

    # Note: to make minimal changes to the existing pyodide-build entrypoint,
    #       keep arguments of buildall unghanged.
    # TODO: refactor this when we remove pyodide-build entrypoint.
    args = argparse.Namespace(**ctx.params)
    args.dir = args.recipe_dir

    if len(args.packages) == 1 and "," in args.packages[0]:
        # Handle packages passed with old comma separated syntax.
        # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
        args.only = args.packages[0].replace(" ", "")
    else:
        args.only = ",".join(args.packages)

    args = buildall.set_default_args(args)

    pkg_map = buildall.build_packages(recipe_dir_, args)

    if install:
        buildall.install_packages(pkg_map, install_dir_)
