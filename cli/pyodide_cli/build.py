from pathlib import Path

import rich_click.typer as typer
from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

from . import build_task

app = typer.Typer()


@app.callback(no_args_is_help=True)
def callback():
    """TODO: HELP STRING"""
    return


@app.command("package")
def package(
    name: str,
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
):
    """Build a package"""
    packages_root = Path(root) / "packages"
    package_dir = packages_root / name
    meta_yaml = package_dir / "meta.yaml"
    DoitMain(ModuleTaskLoader(build_task)).run(["package", "--name", str(meta_yaml)])


@app.command("emsdk")
def emsdk():
    """Prepare emsdk"""
    DoitMain(ModuleTaskLoader(build_task)).run(["emsdk"])


@app.command("cpython")
def cpython():
    """Build a cpython"""
    DoitMain(ModuleTaskLoader(build_task)).run(["cpython"])


@app.command("pyodide")
def pyodide(
    packages: str = typer.Option("core", help="The packages to be bundled."),
):
    """Build pyodide"""
    DoitMain(ModuleTaskLoader(build_task)).run(
        ["repodata_json", "--packages", packages]
    )
    DoitMain(ModuleTaskLoader(build_task)).run(["pyodide"])


@app.command("clean")
def clean(target: str):
    """Clean build artifacts"""
    DoitMain(ModuleTaskLoader(build_task)).run(["clean", target])
