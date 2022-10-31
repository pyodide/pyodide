from pathlib import Path

import typer  # type: ignore[import]

from .. import common
from ..out_of_tree import build
from ..out_of_tree.utils import initialize_pyodide_root

app = typer.Typer()


@app.callback(invoke_without_command=True)  # type: ignore[misc]
def main(
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Build packages for Pyodide"""

    # When `pyodide build` is called without any subcommand,
    # it will call out-of-tree build command.
    # This is a hack to make both `pyodide build` and `pyodide build <subcommand>` work.
    build_wheel(exports, ctx)


@app.command("graph")  # type: ignore[misc]
def build_graph(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or * for all packages"
    ),
    output: Path = typer.Option(
        None,
        help="Path to output the dependency graph",
    ),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is `packages` in the root directory.",
    ),
) -> None:
    """Build packages and create repodata.json (in-tree build)"""
    # pyodide_root = common.search_pyodide_root(Path.cwd()) if not root else Path(root)
    # recipe_dir_ = pyodide_root / "packages" if not recipe_dir else Path(recipe_dir)

    # buildall.build_packages()


@app.command("wheel")  # type: ignore[misc]
def build_wheel(
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package (out-of-tree build)"""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = ctx.args
    build.run(exports, backend_flags)


build_wheel.typer_kwargs = {
    "context_settings": {
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
}
