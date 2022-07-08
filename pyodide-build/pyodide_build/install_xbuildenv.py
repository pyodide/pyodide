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
    parser.add_argument("--download", action="store_true", help="Download xbuild env")
    parser.add_argument("xbuild_env", type=str, nargs=1)
    return parser


def download_xbuild_env(version: str, xbuildenv_path: Path) -> None:
    from shutil import rmtree, unpack_archive
    from tempfile import NamedTemporaryFile
    from urllib.request import urlretrieve

    rmtree(xbuildenv_path, ignore_errors=True)
    with NamedTemporaryFile(suffix=".tar") as f:
        urlretrieve(
            f"http://pyodide-cache.s3-website-us-east-1.amazonaws.com/xbuildenv/{version}.tar",
            f.name,
        )
        unpack_archive(f.name, xbuildenv_path)


def install_xbuild_env(xbuildenv_path: Path) -> None:
    xbuildenv_path = xbuildenv_path / "xbuildenv"
    pyodide_root = get_pyodide_root()
    xbuildenv_root = xbuildenv_path / "pyodide-root"
    host_site_packages = xbuildenv_root / Path(
        get_make_flag("HOSTSITEPACKAGES")
    ).relative_to(pyodide_root)
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
    # Copy the site-packages-extras (coming from the cross-build-files meta.yaml
    # key) over the site-packages directory with the newly installed packages.
    shutil.copytree(
        xbuildenv_path / "site-packages-extras", host_site_packages, dirs_exist_ok=True
    )


def main(args: argparse.Namespace) -> None:
    xbuildenv_path = Path(args.xbuild_env[0])
    version = "2"
    if args.download:
        download_xbuild_env(version, xbuildenv_path)
    install_xbuild_env(xbuildenv_path)
