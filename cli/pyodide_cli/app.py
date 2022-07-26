# import os
# import subprocess

import rich_click.typer as typer

from . import __version__, build, package

# from pyodide_build.common import init_environment, search_pyodide_root


app = typer.Typer(add_completion=False)
app.add_typer(package.app, name="package")
app.add_typer(build.app, name="build")


def version_callback(value: bool):
    if value:
        typer.echo(f"Pyodide CLI Version: {__version__}")
        raise typer.Exit()


@app.callback(no_args_is_help=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    """A command line interface for Pyodide."""
    pass


if __name__ == "__main__":
    app()
