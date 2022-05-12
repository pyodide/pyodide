import argparse
import shutil
import subprocess
from pathlib import Path
from sys import version_info

from .common import get_make_flag, get_pyodide_root


def make_parser(parser: argparse.ArgumentParser):
    parser.description = (
        "Install xbuild env.\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the Pyodide Makefile."
    )
    return parser


def main(args):
    pyodide_root = get_pyodide_root()
    host_site_packages = Path(get_make_flag("HOSTSITEPACKAGES"))
    xbuildenv_path = pyodide_root / "xbuildenv"
    major_minor = f"{version_info.major}.{version_info.minor}"
    major_minor_patch = f"{major_minor}.{version_info.micro}"
    include_path = (
        pyodide_root
        / f"cpython/installs/python-{major_minor_patch}/include/python{major_minor}/"
    )
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
        xbuildenv_path / "site_packages", host_site_packages, dirs_exist_ok=True
    )
