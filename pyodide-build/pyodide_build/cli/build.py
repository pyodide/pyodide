import argparse
from pathlib import Path

import typer  # type: ignore[import]

from .. import buildall, common
from ..out_of_tree import build
from ..out_of_tree.utils import initialize_pyodide_root

app = typer.Typer()


@app.callback(invoke_without_command=True)  # type: ignore[misc]
def main(
    exports: str = typer.Option("requested", hidden=True),
    flags: list[str] = typer.Option(None, hidden=True),
    ctx: typer.Context = typer.Context,
) -> None:
    """
    Build packages for Pyodide

    If no subcommand is specified, `wheel` command is used.
    """

    # When `pyodide build` is called without any subcommand,
    # it will call out-of-tree build command.
    # This is a hack to make both `pyodide build` and `pyodide build <subcommand>` work.
    if ctx.invoked_subcommand is not None:
        return

    build_wheel(exports, flags)


@app.command("recipe")  # type: ignore[misc]
def build_recipe(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or * for all packages in recipe directory"
    ),
    output: str = typer.Option(
        None,
        help="Path to output built packages and repodata.json. "
        "If not specified, the default is `PYODIDE_ROOT/dist`.",
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
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is `packages` in the root directory.",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Build packages using yaml recipes and create repodata.json"""
    pyodide_root = common.search_pyodide_root(Path.cwd()) if not root else Path(root)
    recipe_dir_ = pyodide_root / "packages" if not recipe_dir else Path(recipe_dir)
    output_dir = pyodide_root / "dist" if not output else Path(output)

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

    buildall.build_packages(recipe_dir_, output_dir, args)


@app.command("wheel")  # type: ignore[misc]
def build_wheel(
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    flags: list[str] = typer.Option(None, help="Build flags passed to pypa/build"),
) -> None:
    """Use pypa/build to build a Python package"""
    initialize_pyodide_root()
    common.check_emscripten_version()
    build.run(exports, flags)
