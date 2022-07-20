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


# def get_config(config_file):
#     # TODO: use standalone config file instead of Makefile.env
#     # Note that we don't want to use pyodide_build.common.init_environment()
#     # because it override some unrelated env variables (BASH_SOURCE, ...) that causes build error.

#     PYODIDE_ROOT = search_pyodide_root(os.getcwd())
#     environment = {
#         "PYODIDE_ROOT": str(PYODIDE_ROOT),
#     }
#     result = subprocess.run(
#         ["make", "-f", str(PYODIDE_ROOT / config_file), ".output_vars"],
#         capture_output=True,
#         text=True,
#         env=environment,
#     )
#     for line in result.stdout.splitlines():
#         equalPos = line.find("=")
#         if equalPos != -1:
#             varname = line[0:equalPos]
#             value = line[equalPos + 1 :]
#             value = value.strip("'").strip()
#             environment[varname] = value

#     return environment


@app.callback(no_args_is_help=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", callback=version_callback, is_eager=True
    ),
):
    pass
    # init_environment()
    # new_env = os.environ.copy()
    # os.environ.clear()

    # vars = [
    #     "PATH",
    #     "PYTHONPATH",
    #     "PYODIDE_ROOT",
    #     "PYTHONINCLUDE",
    #     "NUMPY_LIB",
    #     "PYODIDE_PACKAGE_ABI",
    #     "HOME",
    #     "HOSTINSTALLDIR",
    #     "TARGETINSTALLDIR",
    #     "SYSCONFIG_NAME",
    #     "HOSTSITEPACKAGES",
    #     "PYMAJOR",
    #     "PYMINOR",
    #     "PYMICRO",
    #     "CPYTHONBUILD",
    #     "SIDE_MODULE_CFLAGS",
    #     "SIDE_MODULE_LDFLAGS",
    #     "STDLIB_MODULE_CFLAGS",
    #     "UNISOLATED_PACKAGES",
    #     "WASM_LIBRARY_DIR",
    #     "WASM_PKG_CONFIG_PATH",
    #     "CARGO_BUILD_TARGET",
    #     "CARGO_HOME",
    #     "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    #     "RUSTFLAGS",
    #     "PYO3_CONFIG_FILE",
    # ] + ["CPYTHONLIB", "MAIN_MODULE_CFLAGS", "MAIN_MODULE_LDFLAGS", "PYODIDE_BASE_URL"]
    # for var in vars:
    #     os.environ[var] = new_env[var]


if __name__ == "__main__":
    app()
