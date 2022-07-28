from contextlib import redirect_stdout
from io import StringIO

import typer  # type: ignore[import]
from doit.cmd_base import ModuleTaskLoader  # type: ignore[import]
from doit.doit_cmd import DoitMain  # type: ignore[import]

from .. import doit_tasks

app = typer.Typer()
runner = DoitMain(ModuleTaskLoader(doit_tasks))


@app.callback(no_args_is_help=True)  # type: ignore[misc]
def callback() -> None:
    """Build Pyodide core and packages"""
    return


@app.command("package")  # type: ignore[misc]
def package(
    name: str,
) -> None:
    """Build a package"""
    return runner.run([f"package:{name}"])


@app.command("emsdk")  # type: ignore[misc]
def emsdk() -> None:
    """Prepare emsdk"""
    return runner.run(["emsdk"])


@app.command("cpython")  # type: ignore[misc]
def cpython() -> None:
    """Build a cpython"""
    return runner.run(["cpython"])


@app.command("pyodide")  # type: ignore[misc]
def pyodide(
    packages: str = typer.Option("core", help="The packages to be bundled."),
) -> None:
    """Build pyodide"""
    runner.run(["repodata_json", "--packages", packages])
    return runner.run(["pyodide"])


@app.command("clean")  # type: ignore[misc]
def clean(
    target: str = typer.Argument("pyodide", help="The target to be cleaned."),
    all: bool = typer.Option(False, help="Clean all targets."),
) -> None:
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


@app.command("build")  # type: ignore[misc]
def build(
    target: str,
) -> None:
    # for debugging
    # TODO: remove this task
    return runner.run([target])
