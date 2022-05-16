import rich_click.typer as typer

app = typer.Typer()


@app.callback(no_args_is_help=True)
def callback():
    return


@app.command("serve")
def serve(
    dir: str = typer.Argument("dist", help="The directory to serve."),
    port: int = typer.Option(8000, help="The port to serve on."),
    open_console: bool = typer.Option(False, help="Open the browser console."),
):
    """
    Serve a Pyodide distribution
    """
    raise NotImplementedError()
