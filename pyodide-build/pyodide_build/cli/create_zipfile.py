from pathlib import Path

import typer

from ..pyzip import create_zipfile


def main(
    libdir: list[Path] = typer.Argument(
        ...,
        help="List of paths to the directory containing the Python standard library or extra packages.",
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
    create_zipfile(
        libdir,
        output,
        pycompile=pycompile,
        filterfunc=None,
        compression_level=compression_level,
    )
    typer.echo(f"Zip file created at {output.resolve()}")


main.typer_kwargs = {"hidden": True}  # type: ignore[attr-defined]
