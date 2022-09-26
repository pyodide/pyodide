from pathlib import Path

import typer  # type: ignore[import]

from ..out_of_tree import venv
from ..out_of_tree.utils import initialize_pyodide_root


def main(
    dest: Path = typer.Argument(
        ...,
        help="directory to create virtualenv at",
    ),
) -> None:
    """Create a Pyodide virtual environment"""
    initialize_pyodide_root()
    venv.create_pyodide_venv(dest)
