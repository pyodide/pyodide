import argparse
import shutil
import subprocess
from pathlib import Path

from .common import get_make_flag, get_pyodide_root


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Install xbuild env.\n\n"
        "The installed environment is the same as the one that would result from\n"
        "`PYODIDE_PACKAGES='scipy' make` except that it is much faster.\n"
        "The goal is to enable out-of-tree builds for binary packages that depend\n"
        "on numpy or scipy.\n"
        "Note: this is a private endpoint that should not be used outside of the Pyodide Makefile."
    )
    return parser


def main(args: argparse.Namespace) -> None:
    pyodide_root = get_pyodide_root()
    host_site_packages = Path(get_make_flag("HOSTSITEPACKAGES"))
    xbuildenv_path = pyodide_root / "xbuildenv"
    include_path = Path(get_make_flag("PYTHONINCLUDE"))
    include_path.mkdir(exist_ok=True, parents=True)
    shutil.copytree(xbuildenv_path / "python-include", include_path, dirs_exist_ok=True)
    host_site_packages.mkdir(exist_ok=True, parents=True)
    subprocess.run(
        [
            "pip",
            "install",
            "-t",
            host_site_packages,
            "-r",
            xbuildenv_path / "requirements.txt",
        ]
    )
    shutil.copytree(
        xbuildenv_path / "site-packages", host_site_packages, dirs_exist_ok=True
    )
