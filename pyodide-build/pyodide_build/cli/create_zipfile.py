import re
from pathlib import Path

import typer

from ..pyzip import create_zipfile


def main(
    libdir: list[Path] = typer.Argument(
        ...,
        help="List of paths to the directory containing the Python standard library or extra packages.",
    ),
    exclude: str = typer.Option(
        "",
        help="List of files to exclude from the zip file. Defaults to no files.",
    ),
    stub: str = typer.Option(
        "",
        help="List of files that are replaced by JS implementations. Defaults to no files.",
    ),
    pycompile: bool = typer.Option(
        False, help="Whether to compile the .py files into .pyc."
    ),
    output: Path = typer.Option(
        "python.zip", help="Path to the output zip file. Defaults to python.zip."
    ),
    compression_level: int = typer.Option(
        6, help="Compression level to use for the created zip file"
    ),
) -> None:
    """
    Bundle Python standard libraries into a zip file.
    """

    # Convert the comma / space separated strings to lists
    excludes = [
        item.strip() for item in re.split(r",|\s", exclude) if item.strip() != ""
    ]
    stubs = [item.strip() for item in re.split(r",|\s", stub) if item.strip() != ""]

    create_zipfile(
        libdir,
        excludes,
        stubs,
        output,
        pycompile=pycompile,
        filterfunc=None,
        compression_level=compression_level,
    )
    typer.echo(f"Zip file created at {output.resolve()}")


main.typer_kwargs = {"hidden": True}  # type: ignore[attr-defined]
