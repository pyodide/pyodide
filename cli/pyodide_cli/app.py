# import os
# import subprocess
from importlib.metadata import entry_points

import typer

from . import __version__

# from pyodide_build.common import init_environment, search_pyodide_root


app = typer.Typer(add_completion=False)


def version_callback(value: bool):
    if value:
        typer.echo(f"Pyodide CLI Version: {__version__}")
        raise typer.Exit()


@app.callback(no_args_is_help=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    """A command line interface for Pyodide."""
    pass


def _register_callable(func, name):
    @app.command(
        name,
        help=func.__doc__,
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def _cmd(
        help: bool = typer.Option(False),
        ctx: typer.Context = typer.Context,
    ):
        if help:
            typer.echo(ctx.get_help())
            raise typer.Exit()
        else:
            func(*ctx.args)


def register_plugins():
    eps = entry_points(group="pyodide.cli")
    plugins = {ep.name: ep.load() for ep in eps}
    for plugin_name, module in plugins.items():
        if isinstance(module, typer.Typer):
            app.add_typer(module, name=plugin_name)
        elif callable(module):
            _register_callable(module, plugin_name)
        else:
            raise RuntimeError(f"Invalid plugin: {plugin_name}")


def main():
    register_plugins()
    app()


if __name__ == "__main__":
    main()
