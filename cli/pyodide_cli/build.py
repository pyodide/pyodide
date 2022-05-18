from pathlib import Path

import rich_click.typer as typer
from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

from . import task

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
    DoitMain(ModuleTaskLoader(task)).run(["build_package", "--name", str(meta_yaml)])


@app.command("cpython")
def cpython():
    """Build a cpython"""
    DoitMain(ModuleTaskLoader(task)).run(["build_cpython"])


@app.command("pyodide-core")
def pyodide_core():
    """Build pyodide"""
    DoitMain(ModuleTaskLoader(task)).run(["build_pyodide_core"])


@app.command("pyodide-js")
def pyodide_js():
    """Build pyodide"""
    DoitMain(ModuleTaskLoader(task)).run(["build_pyodide_js"])


@app.command("pyodide-asm-js")
def pyodide_asm_js():
    """Build pyodide"""
    DoitMain(ModuleTaskLoader(task)).run(["build_pyodide_asm_js"])
