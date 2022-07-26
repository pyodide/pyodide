from enum import Enum
from pathlib import Path

import rich_click.typer as typer

import pyodide_build.common
import pyodide_build.mkpkg

app = typer.Typer()


class PackageFormat(str, Enum):
    wheel = "wheel"
    sdist = "sdist"


@app.callback(no_args_is_help=True)
def callback():
    """Add a new package or update an existing package"""
    return


@app.command("new")
def new_package(
    name: str,
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: PackageFormat = typer.Option(
        None,
        help="Which source format is preferred. Options are wheel or sdist. "
        "If none is provided, then either a wheel or an sdist will be used. ",
    ),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
):
    """
    Create a new package.
    """
    if root is None:
        root = pyodide_build.common.search_pyodide_root(Path.cwd())

    pyodide_build.mkpkg.make_package(
        Path(root) / "packages", name, version, source_fmt=source_format
    )


@app.command("update")
def update_package(
    name: str,
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: PackageFormat = typer.Option(
        None,
        help="Which source format is preferred. Options are wheel or sdist. "
        "If none is provided, the type will be kept the same if possible.",
    ),
    update_patched: bool = typer.Option(
        False, help="Force update the package even if it contains patches."
    ),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
):
    """
    Update an existing package.
    """
    if root is None:
        root = pyodide_build.common.search_pyodide_root(Path.cwd())

    pyodide_build.mkpkg.update_package(
        Path(root) / "packages",
        name,
        version,
        source_fmt=source_format,
        updated_patched=update_patched,
    )
