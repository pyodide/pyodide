import argparse
import json
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen, urlretrieve

from .common import exit_with_stdio, get_make_flag, get_pyodide_root
from .create_pypa_index import create_pypa_index


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
    parser.add_argument("xbuildenv", type=str, nargs=1)
    return parser


def download_xbuildenv(version: str, xbuildenv_path: Path) -> None:
    from shutil import rmtree, unpack_archive
    from tempfile import NamedTemporaryFile

    print("Downloading xbuild environment")
    rmtree(xbuildenv_path, ignore_errors=True)
    with NamedTemporaryFile(suffix=".tar") as f:
        urlretrieve(
            f"https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2",
            f.name,
        )
        unpack_archive(f.name, xbuildenv_path)


def install_xbuildenv(version: str, xbuildenv_path: Path) -> None:
    print("Installing xbuild environment")
    xbuildenv_path = xbuildenv_path / "xbuildenv"
    pyodide_root = get_pyodide_root()
    xbuildenv_root = xbuildenv_path / "pyodide-root"
    host_site_packages = xbuildenv_root / Path(
        get_make_flag("HOSTSITEPACKAGES")
    ).relative_to(pyodide_root)
    host_site_packages.mkdir(exist_ok=True, parents=True)
    result = subprocess.run(
        [
            "pip",
            "install",
            "-t",
            host_site_packages,
            "-r",
            xbuildenv_path / "requirements.txt",
        ],
        capture_output=True,
        encoding="utf8",
    )
    if result.returncode != 0:
        exit_with_stdio(result)
    # Copy the site-packages-extras (coming from the cross-build-files meta.yaml
    # key) over the site-packages directory with the newly installed packages.
    shutil.copytree(
        xbuildenv_path / "site-packages-extras", host_site_packages, dirs_exist_ok=True
    )
    cdn_base = f"https://cdn.jsdelivr.net/pyodide/v{version}/full/"
    if (xbuildenv_root / "repodata.json").exists():
        repodata_bytes = (xbuildenv_root / "repodata.json").read_bytes()
    else:
        repodata_url = cdn_base + "repodata.json"
        with urlopen(repodata_url) as response:
            repodata_bytes = response.read()
    repodata = json.loads(repodata_bytes)
    version = repodata["info"]["version"]
    create_pypa_index(repodata["packages"], xbuildenv_root, cdn_base)


def main(args: argparse.Namespace) -> None:
    from . import __version__

    xbuildenv_path = Path(args.xbuildenv[0])
    version = __version__
    if args.download:
        download_xbuildenv(version, xbuildenv_path)
    install_xbuildenv(version, xbuildenv_path)
