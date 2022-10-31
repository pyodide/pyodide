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


@app.command("graph")
def build_graph():
    """Build the dependency graph for the packages (in-tree build)."""
    pass


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
