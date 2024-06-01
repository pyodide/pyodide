from pathlib import Path

import typer

from ..common import xbuildenv_dirname
from ..xbuildenv import CrossBuildEnvManager

DIRNAME = xbuildenv_dirname()

app = typer.Typer(hidden=True, no_args_is_help=True)


@app.callback()
def callback():
    """
    Manage cross-build environment for building packages for Pyodide.
    """


def check_xbuildenv_root(path: Path) -> None:
    if not path.is_dir():
        typer.echo(f"Cross-build environment not found in {path.resolve()}")
        raise typer.Exit(1)


@app.command("install")
def _install(
    version: str = typer.Argument(
        None, help="version of cross-build environment to install"
    ),
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
    url: str = typer.Option(None, help="URL to download cross-build environment from"),
) -> None:
    """
    Install cross-build environment.

    The installed environment is the same as the one that would result from
    `PYODIDE_PACKAGES='scipy' make` except that it is much faster.
    The goal is to enable out-of-tree builds for binary packages that depend
    on numpy or scipy.
    """
    manager = CrossBuildEnvManager(path)

    if url:
        manager.install(url=url)
    else:
        manager.install(version=version)

    typer.echo(f"Pyodide cross-build environment installed at {path.resolve()}")


@app.command("version")
def _version(
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Print current version of cross-build environment.
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    version = manager.current_version
    if not version:
        typer.echo("No version selected")
        raise typer.Exit(1)
    else:
        typer.echo(version)


@app.command("versions")
def _versions(
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Print all installed versions of cross-build environment.
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    versions = manager.list_versions()
    current_version = manager.current_version

    for version in versions:
        if version == current_version:
            typer.echo(f"* {version}")
        else:
            typer.echo(f"  {version}")


@app.command("uninstall")
def _uninstall(
    version: str = typer.Argument(
        None, help="version of cross-build environment to uninstall"
    ),
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Uninstall cross-build environment.
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    manager.uninstall_version(version)
    typer.echo(f"Pyodide cross-build environment {version} uninstalled")


@app.command("use")
def _use(
    version: str = typer.Argument(
        ..., help="version of cross-build environment to use"
    ),
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Select a version of cross-build environment to use.
    """
    check_xbuildenv_root(path)
    manager = CrossBuildEnvManager(path)
    manager.use_version(version)
    typer.echo(f"Pyodide cross-build environment {version} is now in use")
