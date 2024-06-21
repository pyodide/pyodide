from pathlib import Path

import typer

from ..build_env import local_versions
from ..common import xbuildenv_dirname
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

    table = []
    columns = [
        # column name, width
        ("Version", 10),
        ("Python", 10),
        ("Emscripten", 10),
        ("pyodide-build", 25),
        ("Compatible", 10),
    ]
    header = [f"{name:{width}}" for name, width in columns]
    divider = ["-" * width for _, width in columns]

    table.append("\t".join(header))
    table.append("\t".join(divider))

    for release in releases:
        compatible = (
            "Yes"
            if release.is_compatible(
                python_version=local["python"],
                pyodide_build_version=local["pyodide-build"],
            )
            else "No"
        )
        pyodide_build_range = f"{release.min_pyodide_build_version or ''} - {release.max_pyodide_build_version or ''}"

        row = [
            f"{release.version:{columns[0][1]}}",
            f"{release.python_version:{columns[1][1]}}",
            f"{release.emscripten_version:{columns[2][1]}}",
            f"{pyodide_build_range:{columns[3][1]}}",
            f"{compatible:{columns[4][1]}}",
        ]

        table.append("\t".join(row))

    print("\n".join(table))
