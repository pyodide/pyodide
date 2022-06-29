import argparse
import shutil
import subprocess
from pathlib import Path

from .common import get_make_flag, get_pyodide_root
from .io import parse_package_config


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
    xbuild_site_packages = xbuildenv_path / "site-packages-extras"
    for pkg in (PYODIDE_ROOT / "packages").glob("**/meta.yaml"):
        config = parse_package_config(pkg, check=False)
        xbuild_files = config.get("build", {}).get("cross-build-files", [])
        for path in xbuild_files:
            target = xbuild_site_packages / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(site_packages / path, target)


def get_relative_path(pyodide_root, flag):
    return Path(get_make_flag(flag)).relative_to(pyodide_root)


def main(args):
    pyodide_root = get_pyodide_root()
    pythoninclude = get_relative_path(pyodide_root, "PYTHONINCLUDE")
    wasm_lib_dir = get_relative_path(pyodide_root, "WASM_LIBRARY_DIR")
    sysconfig_dir = get_relative_path(pyodide_root, "SYSCONFIGDATA_DIR")
    xbuildenv_path = pyodide_root / "xbuildenv"
    shutil.rmtree(xbuildenv_path, ignore_errors=True)

    xbuildenv_root = xbuildenv_path / "pyodide-root"
    xbuildenv_path.mkdir()
    to_copy: list[Path] = [
        pythoninclude,
        sysconfig_dir,
        Path("Makefile.envs"),
        wasm_lib_dir / "CLAPACK",
        wasm_lib_dir / "cmake",
    ]
    # Some ad-hoc stuff here to moderate size. We'd like to include all of
    # wasm_lib_dir but there's 180mb of it. Better to leave out all the video
    # codecs and stuff.
    for pkg in ["ssl", "libcrypto", "zlib", "xml", "mpfr"]:
        to_copy.extend(
            x.relative_to(pyodide_root)
            for x in (pyodide_root / wasm_lib_dir / "include").glob(f"**/*{pkg}*")
            if "boost" not in str(x)
        )
        to_copy.extend(
            x.relative_to(pyodide_root)
            for x in (pyodide_root / wasm_lib_dir / "lib").glob(f"**/*{pkg}*")
        )

    for path in to_copy:
        if (pyodide_root / path).is_dir():
            shutil.copytree(
                pyodide_root / path, xbuildenv_root / path, dirs_exist_ok=True
            )
        else:
            (xbuildenv_root / path).parent.mkdir(exist_ok=True, parents=True)
            shutil.copy(pyodide_root / path, xbuildenv_root / path)

    copy_xbuild_files(xbuildenv_path)
    res = subprocess.run(
        ["pip", "freeze", "--path", get_make_flag("HOSTSITEPACKAGES")],
        stdout=subprocess.PIPE,
    )
    (xbuildenv_path / "requirements.txt").write_bytes(res.stdout)
