from pathlib import Path


def loadable_path() -> str:
    """Return the path of the SQLite extension to pass to ``load_extension``."""
    [path] = Path(__file__).parent.glob("_sqlite_ext*.so")
    return str(path)


def load(conn) -> None:
    conn.load_extension(loadable_path())
