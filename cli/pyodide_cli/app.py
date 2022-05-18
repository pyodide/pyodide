import os
import subprocess

import rich_click.typer as typer

from pyodide_build.common import init_environment, search_pyodide_root

from . import __version__, build, package

app = typer.Typer(add_completion=False)
app.add_typer(package.app, name="package")
app.add_typer(build.app, name="build")


def version_callback(value: bool):
    if value:
        typer.echo(f"Pyodide CLI Version: {__version__}")
        raise typer.Exit()


def get_config(config_file):
    # TODO: use standalone config file instead of Makefile.env
    # Note that we don't want to use pyodide_build.common.init_environment()
    # because it override some unrelated env variables (BASH_SOURCE, ...) that causes build error.

    PYODIDE_ROOT = search_pyodide_root(os.getcwd())
    environment = {
        "PYODIDE_ROOT": str(PYODIDE_ROOT),
    }
    result = subprocess.run(
        ["make", "-f", str(PYODIDE_ROOT / config_file), ".output_vars"],
        capture_output=True,
        text=True,
        env=environment,
    )
    for line in result.stdout.splitlines():
        equalPos = line.find("=")
        if equalPos != -1:
            varname = line[0:equalPos]
            value = line[equalPos + 1 :]
            value = value.strip("'").strip()
            environment[varname] = value

    return environment


@app.callback(no_args_is_help=True)
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    init_environment()


if __name__ == "__main__":
    app()
