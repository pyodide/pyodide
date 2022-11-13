import sys
from pathlib import Path

import typer  # type: ignore[import]

from pyodide_build._py_compile import _py_compile_wheel


def main(
    wheel_path: Path = typer.Argument(..., help="Path to the input wheel"),
) -> None:
    """Compile .py files to .pyc in a wheel"""
    if wheel_path.suffix != ".whl":
        typer.echo(f"Error: only .whl files are supported, got {wheel_path.name}")
        sys.exit(1)
    _py_compile_wheel(wheel_path, verbose=False)
