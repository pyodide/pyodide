from pathlib import Path

import typer

from ..build_env import init_environment
from ..out_of_tree import venv


def main(
    dest: Path = typer.Argument(
        ...,
        help="directory to create virtualenv at",
    ),
) -> None:
    """Create a Pyodide virtual environment"""
    init_environment()
    venv.create_pyodide_venv(dest)
