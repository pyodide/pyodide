import rich_click.typer as typer

from pyodide_build.common import init_environment

from . import __version__, build, package

app = typer.Typer(add_completion=False)
app.add_typer(package.app, name="package")
app.add_typer(build.app, name="build")


def version_callback(value: bool):
    if value:
        typer.echo(f"Pyodide CLI Version: {__version__}")
        raise typer.Exit()


@app.callback(no_args_is_help=True)
def main(
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    init_environment()


if __name__ == "__main__":
    """
    pyodide builddoc [--serve]
    pyodide package new
    pyodide package list
    pyodide package update
    pyodide serve
    pyodide build python
    pyodide build numpy
    pyodide build api
    pyodide generate
    """

    app()
