import pathlib

path = pathlib.Path(pathlib.__file__).parent / "platform.py"

exec(path.read_text(), globals())


def system():
    return "pyodide"
