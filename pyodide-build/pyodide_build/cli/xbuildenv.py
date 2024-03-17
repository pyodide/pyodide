from pathlib import Path

import typer

from ..common import xbuildenv_dirname
from ..create_xbuildenv import create
from ..logger import logger
from ..xbuildenv import CrossBuildEnvManager

DIRNAME = xbuildenv_dirname()

app = typer.Typer(hidden=True, no_args_is_help=True)


@app.callback()
def callback():
    """
    Create or install cross build environment
    """


@app.command("install")
def _install(
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
    url: str = typer.Option(None, help="URL to download cross-build environment from"),
) -> None:
    """
    Install xbuildenv.

    The installed environment is the same as the one that would result from
    `PYODIDE_PACKAGES='scipy' make` except that it is much faster.
    The goal is to enable out-of-tree builds for binary packages that depend
    on numpy or scipy.
    Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
    """
    manager = CrossBuildEnvManager(path)

    if url:
        manager.install(url=url)
    else:
        manager.install()

    logger.info(f"Pyodide cross-build environment installed at {path.resolve()}")


@app.command("create")
def _create(
    path: Path = typer.Argument(
        DIRNAME, help="path to cross-build environment directory"
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
    logger.info(f"Pyodide cross-build environment created at {path.resolve()}")


@app.command("version")
def _version(
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Print current version of xbuildenv
    """
    manager = CrossBuildEnvManager(path)
    version = manager.current_version
    if not version:
        print("No version selected")
    else:
        print(version)


@app.command("versions")
def _versions(
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Print all installed versions of xbuildenv
    """
    manager = CrossBuildEnvManager(path)
    versions = manager.list_versions()
    current_version = manager.current_version

    for version in versions:
        if version == current_version:
            print(f"* {version}")
        else:
            print(f"  {version}")


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
    Uninstall xbuildenv.
    """
    manager = CrossBuildEnvManager(path)
    manager.uninstall_version(version)
    logger.info(f"Pyodide cross-build environment {version} uninstalled")


@app.command("use")
def _use(
    version: str = typer.Argument(..., help="version of xbuildenv to use"),
    path: Path = typer.Option(
        DIRNAME, help="path to cross-build environment directory"
    ),
) -> None:
    """
    Use xbuildenv.
    """
    manager = CrossBuildEnvManager(path)
    manager.use_version(version)
    logger.info(f"Pyodide cross-build environment {version} is now in use")
