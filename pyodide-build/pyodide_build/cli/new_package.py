from pathlib import Path

import typer  # type: ignore[import]

from .. import common, mkpkg

app = typer.Typer()


@app.callback(no_args_is_help=True)  # type: ignore[misc]
def callback() -> None:
    """Add a new package or update an existing package"""
    return


@app.command("new")  # type: ignore[misc]
def new_package(
    name: str,
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: str = typer.Option(
        None,
        help="Which source format is preferred. Options are wheel or sdist. "
        "If none is provided, then either a wheel or an sdist will be used. ",
    ),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
) -> None:
    """
    Create a new package.
    """

    # FIXME: root can be None but typer does not support complex type annoations...
    if root is None:
        root = common.search_pyodide_root(Path.cwd())  # type: ignore[unreachable]

    mkpkg.make_package(Path(root) / "packages", name, version, source_fmt=source_format)  # type: ignore[arg-type]


@app.command("update")  # type: ignore[misc]
def update_package(
    name: str,
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: str = typer.Option(
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
) -> None:
    """
    Update an existing package.
    """

    # FIXME: root can be None but typer does not support complex type annoations...
    if root is None:
        root = common.search_pyodide_root(Path.cwd())  # type: ignore[unreachable]

    mkpkg.update_package(
        Path(root) / "packages",
        name,
        version,
        source_fmt=source_format,  # type: ignore[arg-type]
        update_patched=update_patched,
    )
