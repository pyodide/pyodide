import rich_click.typer as typer

app = typer.Typer()


@app.callback(no_args_is_help=True)
def callback():
    return


@app.command("build")
def build():
    raise NotImplementedError()


@app.command("serve")
def serve():
    raise NotImplementedError()
