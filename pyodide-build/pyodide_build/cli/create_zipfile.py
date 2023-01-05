from pathlib import Path

import typer  # type: ignore[import]

from ..pyzip import create_zip as _create_zip


def create_zipfile(
    libdir: Path = typer.Argument(
        ..., help="Path to the directory containing the Python standard library."
    ),
    pycompile: bool = typer.Option(
        False, help="Whether to compile the .py files into .pyc."
    ),
    output: Path = typer.Option(
        "python.zip", help="Path to the output zip file. Defaults to python.zip."
    ),
) -> None:
    """
    Bundle Python standard libraries into a zip file.
    """
    _create_zip(libdir, output, pycompile=pycompile, filterfunc=None)
    typer.echo(f"Zip file created at {output}")
