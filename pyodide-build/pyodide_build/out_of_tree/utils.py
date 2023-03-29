import os
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path

from ..common import search_pyodide_root


def ensure_env_installed(env: Path, *, quiet: bool = False) -> None:
    if env.exists():
        return
    from .. import __version__
    from ..install_xbuildenv import download_xbuildenv, install_xbuildenv

    if "dev" in __version__:
        raise RuntimeError(
            "To use out of tree builds with development Pyodide, you must explicitly set PYODIDE_ROOT"
        )

    with ExitStack() as stack:
        if quiet:
            # Prevent writes to stdout
            stack.enter_context(redirect_stdout(StringIO()))

        download_xbuildenv(__version__, env)
        install_xbuildenv(__version__, env)


def initialize_pyodide_root(*, quiet: bool = False) -> None:
    if "PYODIDE_ROOT" in os.environ:
        return
    try:
        os.environ["PYODIDE_ROOT"] = str(search_pyodide_root(Path.cwd()))
        return
    except FileNotFoundError:
        pass
    env = Path(".pyodide-xbuildenv")
    os.environ["PYODIDE_ROOT"] = str(env / "xbuildenv/pyodide-root")
    ensure_env_installed(env, quiet=quiet)
