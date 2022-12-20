import typer  # type: ignore[import]

from ..common import get_make_environment_vars
from ..out_of_tree.utils import initialize_pyodide_root


def main(
    config_var: str = typer.Argument(
        "ALL", help="config variables used in Pyodide", show_default=False
    ),
) -> None:
    """
    Show config variables used in pyodide

    Usage:

    - pyodide config: show all config variables

    - pyodide config <config_var>: show the value of the config variable
    """

    initialize_pyodide_root()

    configs: dict[str, str] = get_make_environment_vars()

    if config_var == "ALL":
        for k, v in configs.items():
            print(f"{k}={v}")
    else:
        print(get_make_environment_vars()[config_var])
