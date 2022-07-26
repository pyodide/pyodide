# from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO

import rich_click.typer as typer
from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

from pyodide_build import doit_tasks

app = typer.Typer()
runner = DoitMain(ModuleTaskLoader(doit_tasks))


@app.callback(no_args_is_help=True)
def callback():
    """Build Pyodide core and packages"""
    return


@app.command("package")
def package(
    name: str,
):
    """Build a package"""
    return runner.run([f"package:{name}"])


@app.command("emsdk")
def emsdk():
    """Prepare emsdk"""
    return runner.run(["emsdk"])


@app.command("cpython")
def cpython():
    """Build a cpython"""
    return runner.run(["cpython"])


@app.command("pyodide")
def pyodide(
    packages: str = typer.Option("core", help="The packages to be bundled."),
):
    """Build pyodide"""
    runner.run(["repodata_json", "--packages", packages])
    return runner.run(["pyodide"])


@app.command("clean")
def clean(
    target: str = typer.Argument("pyodide", help="The target to be cleaned."),
    all: bool = typer.Option(False, help="Clean all targets."),
):
    """Clean build artifacts"""
    if all:
        stream = StringIO()
        with redirect_stdout(stream):
            runner.run(["list"])

        tasks = stream.getvalue().strip().split()
        for task in tasks:
            runner.run(["clean", task])
    else:
        return runner.run(["clean", target])


@app.command("build")
def build(
    target: str,
):
    # for debugging
    # TODO: remove this task
    return runner.run([target])
