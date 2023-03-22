import sys
from pathlib import Path

import typer

from pyodide_build._py_compile import _py_compile_wheel


def main(
    wheel_path: Path = typer.Argument(..., help="Path to the input wheel"),
    compression_level: int = typer.Option(
        6, help="Compression level to use for the created zip file"
    ),
) -> None:
    """Compile .py files to .pyc in a wheel"""
    if wheel_path.suffix != ".whl":
        typer.echo(f"Error: only .whl files are supported, got {wheel_path.name}")
        sys.exit(1)
    _py_compile_wheel(wheel_path, verbose=False, compression_level=compression_level)
