# Create or update a package recipe skeleton,
# inspired from `conda skeleton` command.

import sys
from pathlib import Path

import typer

from .. import build_env, mkpkg
from ..logger import logger

app = typer.Typer()


@app.callback(no_args_is_help=True)
def callback() -> None:
    """Add a new package build recipe or update an existing recipe"""
    return


@app.command("pypi")
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
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages."
        "If not specified, the default is ``<cwd>/packages``.",
    ),
) -> None:
    """
    Create a new package from PyPI.
    """

    if recipe_dir:
        recipe_dir_ = Path(recipe_dir)
    else:
        cwd = Path.cwd()

        try:
            root = build_env.search_pyodide_root(cwd)
        except FileNotFoundError:
            root = cwd

        if build_env.in_xbuildenv():
            root = cwd

        recipe_dir_ = root / "packages"

    if update or update_patched:
        try:
            mkpkg.update_package(
                recipe_dir_,
                name,
                version,
                source_fmt=source_format,  # type: ignore[arg-type]
                update_patched=update_patched,
            )
        except mkpkg.MkpkgFailedException as e:
            logger.error(f"{name} update failed: {e}")
            sys.exit(1)
        except mkpkg.MkpkgSkipped as e:
            logger.warn(f"{name} update skipped: {e}")
        except Exception:
            print(name)
            raise
    else:
        mkpkg.make_package(recipe_dir_, name, version, source_fmt=source_format)  # type: ignore[arg-type]
