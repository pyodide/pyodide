from pathlib import Path

import typer

from ..install_xbuildenv import install

app = typer.Typer(hidden=True)


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

    The isntalled environment is the same as the one that would result from
    `PYODIDE_PACKAGES='scipy' make` except that it is much faster.
    The goal is to enable out-of-tree builds for binary packages that depend
    on numpy or scipy.
    Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
    """
    install(path, download=download, url=url)
