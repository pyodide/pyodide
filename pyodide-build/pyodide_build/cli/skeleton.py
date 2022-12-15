# Create or update a package recipe skeleton,
# inspired from `conda skeleton` command.

from pathlib import Path

import typer  # type: ignore[import]

from .. import common, mkpkg

app = typer.Typer()


@app.callback(no_args_is_help=True)  # type: ignore[misc]
def callback() -> None:
    """Add a new package build recipe or update an existing recipe"""
    return


@app.command("pypi")  # type: ignore[misc]
def new_recipe_pypi(
    name: str,
    update: bool = typer.Option(
        False,
        "--update",
        "-u",
        help="Update an existing recipe instead of creating a new one",
    ),
    update_patched: bool = typer.Option(
        False,
        "--update-patched",
        help="Force update the package even if it contains patches.",
    ),
    version: str = typer.Option(
        None,
        help="The version of the package, if not specified, latest version will be used.",
    ),
    source_format: str = typer.Option(
        None,
        help="Which source format is preferred. Options are wheel or sdist. "
        "If not specified, then either a wheel or an sdist will be used. ",
    ),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is `packages` in the root directory.",
    ),
) -> None:
    """
    Create a new package from PyPI.
    """
    pyodide_root = common.search_pyodide_root(Path.cwd()) if not root else Path(root)
    recipe_dir_ = pyodide_root / "packages" if not recipe_dir else Path(recipe_dir)

    if update or update_patched:
        mkpkg.update_package(
            recipe_dir_,
            name,
            version,
            source_fmt=source_format,  # type: ignore[arg-type]
            update_patched=update_patched,
        )
    else:
        mkpkg.make_package(recipe_dir_, name, version, source_fmt=source_format)  # type: ignore[arg-type]
