from pathlib import Path

import typer

from pyodide_build._py_compile import _py_compile_archive, _py_compile_archive_dir


def main(
    path: Path = typer.Argument(
        ..., help="Path to the input wheel or a folder with wheels or zip files."
    ),
    silent: bool = typer.Option(False, help="Silent mode, do not print anything."),
    keep: bool = typer.Option(False, help="Keep the original wheel / zip file."),
    compression_level: int = typer.Option(
        6, help="Compression level to use for the created zip file"
    ),
) -> None:
    """Compile .py files to .pyc in a wheel, a zip file, or a folder with wheels or zip files.

    If the provided folder contains the `pyodide-lock.json` file, it will be
    rewritten with the updated wheel / zip file paths and sha256 checksums.
    """
    if not path.exists():
        typer.echo(f"Error: {path} does not exist")
        raise typer.Exit(1)

    if path.is_file():
        if path.suffix not in [".whl", ".zip"]:
            typer.echo(
                f"Error: only .whl and .zip files are supported, got {path.name}"
            )
            raise typer.Exit(1)

        _py_compile_archive(
            path, verbose=not silent, keep=keep, compression_level=compression_level
        )
    elif path.is_dir():
        _py_compile_archive_dir(
            path, verbose=not silent, keep=keep, compression_level=compression_level
        )
    else:
        typer.echo(f"{path=} is not a file or a directory")
