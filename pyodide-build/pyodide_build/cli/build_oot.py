import typer  # type: ignore[import]

from .. import common
from ..out_of_tree import build
from ..out_of_tree.utils import initialize_pyodide_root


def main(
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package"""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = ctx.args
    build.run(exports, backend_flags)


main.typer_kwargs = {  # type: ignore[attr-defined]
    "context_settings": {
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
}
