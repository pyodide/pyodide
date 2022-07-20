# from pathlib import Path

import rich_click.typer as typer
from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

from pyodide_build import doit_tasks

app = typer.Typer()
tasks = DoitMain(ModuleTaskLoader(doit_tasks))


@app.callback(no_args_is_help=True)
def callback():
    """TODO: HELP STRING"""
    return


@app.command("package")
def package(
    name: str,
):
    """Build a package"""
    return tasks.run([f"package:{name}"])


@app.command("emsdk")
def emsdk():
    """Prepare emsdk"""
    return tasks.run(["emsdk"])


@app.command("cpython")
def cpython():
    """Build a cpython"""
    return tasks.run(["cpython"])


@app.command("pyodide")
def pyodide(
    packages: str = typer.Option("core", help="The packages to be bundled."),
):
    """Build pyodide"""
    tasks.run(["repodata_json", "--packages", packages])
    return tasks.run(["pyodide"])


@app.command("clean")
def clean(target: str):
    """Clean build artifacts"""
    return tasks.run(["clean", target])
