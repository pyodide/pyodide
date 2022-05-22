import argparse
import shutil
import subprocess
from pathlib import Path

from .common import get_make_flag, get_pyodide_root, parse_package_config


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Create xbuild env.\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the Pyodide Makefile."
    )
    return parser


def copy_xbuild_files(xbuildenv_path):
    PYODIDE_ROOT = get_pyodide_root()
    site_packages = Path(get_make_flag("HOSTSITEPACKAGES"))
    xbuild_site_packages = xbuildenv_path / "site-packages"
    for pkg in (PYODIDE_ROOT / "packages").glob("**/meta.yaml"):
        config = parse_package_config(pkg, check=False)
        xbuild_files = config.get("build", {}).get("cross-build-files", [])
        for path in xbuild_files:
            target = xbuild_site_packages / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(site_packages / path, target)


def main(args):
    pyodide_root = get_pyodide_root()
    xbuildenv_path = pyodide_root / "xbuildenv"
    shutil.rmtree(xbuildenv_path, ignore_errors=True)
    xbuildenv_path.mkdir()
    shutil.copytree(get_make_flag("PYTHONINCLUDE"), xbuildenv_path / "python-include")
    copy_xbuild_files(xbuildenv_path)
    res = subprocess.run(
        ["pip", "freeze", "--path", get_make_flag("HOSTSITEPACKAGES")],
        stdout=subprocess.PIPE,
    )
    (xbuildenv_path / "requirements.txt").write_bytes(res.stdout)
