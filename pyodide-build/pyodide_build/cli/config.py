import typer  # type: ignore[import]

from ..out_of_tree.utils import initialize_pyodide_root


def main(
    config_var: str = typer.Argument("ALL", help="config variables used in Pyodide"),
) -> None:
    """
    Show config variables used in pyodide
    """

    initialize_pyodide_root()
