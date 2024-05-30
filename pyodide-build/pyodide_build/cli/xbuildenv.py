from pathlib import Path

import rich
import typer
from rich.table import Table

from ..build_env import local_versions
from ..common import xbuildenv_dirname
from ..create_xbuildenv import create
from ..xbuildenv import CrossBuildEnvManager
from ..xbuildenv_releases import (
    cross_build_env_metadata_url,
    load_cross_build_env_metadata,
)

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
    force_install: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="force installation even if the version is not compatible",
    ),
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
        manager.install(url=url, force_install=force_install)
    else:
        manager.install(version=version, force_install=force_install)

    typer.echo(f"Pyodide cross-build environment installed at {path.resolve()}")


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
    Create cross-build environment.

    The create environment is then used to cross-compile packages out-of-tree.
    Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
    """

    create(path, pyodide_root=root, skip_missing_files=skip_missing_files)
    typer.echo(f"Pyodide cross-build environment created at {path.resolve()}")


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


@app.command("search")
def _search(
    metadata_path: str = typer.Option(
        None,
        "--metadata",
        help="path to cross-build environment metadata file. It can be a URL or a local file. If not given, the default metadata file is used.",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="search all versions, without filtering out incompatible ones",
    ),
) -> None:
    """
    Search for available versions of cross-build environment.
    """

    # TODO: cache the metadata file somewhere to avoid downloading it every time
    metadata_path = metadata_path or cross_build_env_metadata_url()
    metadata = load_cross_build_env_metadata(metadata_path)
    local = local_versions()

    if show_all:
        releases = metadata.list_compatible_releases()
    else:
        releases = metadata.list_compatible_releases(
            python_version=local["python"],
            pyodide_build_version=local["pyodide-build"],
        )

    if not releases:
        typer.echo(
            "No compatible cross-build environment found for your system. Try using --all to see all versions."
        )
        raise typer.Exit(1)

    table = Table(title="Pyodide cross-build environments")
    table.add_column("Pyodide Version", justify="right")
    table.add_column("Python", justify="right")
    table.add_column("Emscripten", justify="right")
    table.add_column("Compatible pyodide-build Versions", justify="right")
    table.add_column("Compatible", justify="right")

    for release in releases:
        compatible = (
            "Yes"
            if release.is_compatible(
                python_version=local["python"],
                pyodide_build_version=local["pyodide-build"],
            )
            else "No"
        )

        table.add_row(
            release.version,
            release.python_version,
            release.emscripten_version,
            f"{release.min_pyodide_build_version or ''} - {release.max_pyodide_build_version or ''}",
            compatible,
        )

    rich.print(table)
