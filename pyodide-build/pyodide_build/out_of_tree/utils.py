import os
from pathlib import Path

from ..common import search_pyodide_root


def ensure_env_installed(env: Path) -> None:
    if env.exists():
        return
    from .. import __version__
    from ..install_xbuildenv import download_xbuildenv, install_xbuildenv

    if "dev" in __version__:
        raise RuntimeError(
            "To use out of tree builds with development Pyodide, you must explicitly set PYODIDE_ROOT"
        )

    download_xbuildenv(__version__, env)
    install_xbuildenv(__version__, env)


def initialize_pyodide_root() -> None:
    if "PYODIDE_ROOT" in os.environ:
        return
    try:
        os.environ["PYODIDE_ROOT"] = str(search_pyodide_root(__file__))
        return
    except FileNotFoundError:
        pass
    env = Path(".pyodide-xbuildenv")
    os.environ["PYODIDE_ROOT"] = str(env / "xbuildenv/pyodide-root")
    ensure_env_installed(env)
