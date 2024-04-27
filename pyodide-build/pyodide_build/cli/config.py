import typer

from ..build_env import get_build_environment_vars, get_pyodide_root, init_environment

app = typer.Typer(help="Manage config variables used in pyodide")


# A dictionary of config variables {key: env_var_in_makefile}
PYODIDE_CONFIGS = {
    "emscripten_version": "PYODIDE_EMSCRIPTEN_VERSION",
    "python_version": "PYVERSION",
    "rustflags": "RUSTFLAGS",
    "cmake_toolchain_file": "CMAKE_TOOLCHAIN_FILE",
    "pyo3_config_file": "PYO3_CONFIG_FILE",
    "rust_toolchain": "RUST_TOOLCHAIN",
    "cflags": "SIDE_MODULE_CFLAGS",
    "cxxflags": "SIDE_MODULE_CXXFLAGS",
    "ldflags": "SIDE_MODULE_LDFLAGS",
    "meson_cross_file": "MESON_CROSS_FILE",
}


@app.callback(no_args_is_help=True)
def callback() -> None:
    return


def _get_configs() -> dict[str, str]:
    init_environment(quiet=True)

    configs: dict[str, str] = get_build_environment_vars(get_pyodide_root())

    configs_filtered = {k: configs[v] for k, v in PYODIDE_CONFIGS.items()}
    return configs_filtered


@app.command("list")
def list_config():
    """
    List config variables used in pyodide
    """
    configs = _get_configs()

    for k, v in configs.items():
        typer.echo(f"{k}={v}")


@app.command("get")
def get_config(
    config_var: str = typer.Argument(
        ..., help="A config variable to get. Use `list` to see all possible values."
    ),
) -> None:
    """
    Get a value of a single config variable used in pyodide
    """
    configs = _get_configs()

    if config_var not in configs:
        typer.echo(f"Config variable {config_var} not found.")
        typer.Exit(1)

    typer.echo(configs[config_var])
