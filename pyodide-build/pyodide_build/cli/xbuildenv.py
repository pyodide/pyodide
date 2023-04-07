from pathlib import Path

import typer

from ..create_xbuildenv import create
from ..install_xbuildenv import install
from ..logger import logger

app = typer.Typer(hidden=True, no_args_is_help=True)


@app.callback()
def callback():
    """
    Create or install cross build environment
    """


@app.command("install")  # type: ignore[misc]
def _install(
    path: Path = typer.Option(".pyodide-xbuildenv", help="path to xbuildenv directory"),
    download: bool = typer.Option(False, help="download xbuildenv before installing"),
    url: str = typer.Option(None, help="URL to download xbuildenv from"),
) -> None:
    """
    Install xbuildenv.

    The installed environment is the same as the one that would result from
    `PYODIDE_PACKAGES='scipy' make` except that it is much faster.
    The goal is to enable out-of-tree builds for binary packages that depend
    on numpy or scipy.
    Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
    """
    install(path, download=download, url=url)
    logger.info(f"xbuildenv installed at {path.resolve()}")


@app.command("create")  # type: ignore[misc]
def _create(
    path: Path = typer.Argument(
        ".pyodide-xbuildenv", help="path to xbuildenv directory"
    ),
    root: Path = typer.Option(
        None, help="path to pyodide root directory, if not given, will be inferred"
    ),
    skip_missing_files: bool = typer.Option(
        False,
        help="skip if cross build files are missing instead of raising an error. This is useful for testing.",
    ),
) -> None:
    """
    Create xbuildenv.

    The create environment is then used to cross-compile packages out-of-tree.
    Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
    """

    create(path, pyodide_root=root, skip_missing_files=skip_missing_files)
    logger.info(f"xbuildenv created at {path.resolve()}")
