import argparse
import shutil
import subprocess
from pathlib import Path

from .common import (
    exit_with_stdio,
    get_make_flag,
    get_pyodide_root,
    get_unisolated_packages,
)
from .logger import logger
from .recipe import load_all_recipes


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = (
        "Create xbuild env.\n\n"
        "Note: this is a private endpoint that should not be used "
        "outside of the Pyodide Makefile."
    )
    return parser


def copy_xbuild_files(xbuildenv_path: Path) -> None:
    PYODIDE_ROOT = get_pyodide_root()
    site_packages = Path(get_make_flag("HOSTSITEPACKAGES"))
    # Store package cross-build-files into site_packages_extras in the same tree
    # structure as they would appear in the real package.
    # In install_xbuildenv, we will use:
    # pip install -t $HOSTSITEPACKAGES -r requirements.txt
    # cp site-packages-extras $HOSTSITEPACKAGES
    site_packages_extras = xbuildenv_path / "site-packages-extras"
    recipes = load_all_recipes(PYODIDE_ROOT / "packages")
    for recipe in recipes.values():
        xbuild_files = recipe.build.cross_build_files
        for path in xbuild_files:
            target = site_packages_extras / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(site_packages / path, target)


def get_relative_path(pyodide_root: Path, flag: str) -> Path:
    return Path(get_make_flag(flag)).relative_to(pyodide_root)


def copy_wasm_libs(xbuildenv_path: Path) -> None:
    pyodide_root = get_pyodide_root()
    pythoninclude = get_relative_path(pyodide_root, "PYTHONINCLUDE")
    wasm_lib_dir = get_relative_path(pyodide_root, "WASM_LIBRARY_DIR")
    sysconfig_dir = get_relative_path(pyodide_root, "SYSCONFIGDATA_DIR")
    xbuildenv_root = xbuildenv_path / "pyodide-root"
    xbuildenv_path.mkdir(exist_ok=True)
    to_copy: list[Path] = [
        pythoninclude,
        sysconfig_dir,
        Path("Makefile.envs"),
        wasm_lib_dir / "cmake",
        Path("dist/repodata.json"),
        Path("dist/pyodide_py.tar"),
        Path("dist/python"),
    ]
    to_copy.extend(
        x.relative_to(pyodide_root) for x in (pyodide_root / "dist").glob("pyodide.*")
    )
    # Some ad-hoc stuff here to moderate size. We'd like to include all of
    # wasm_lib_dir but there's 180mb of it. Better to leave out all the video
    # codecs and stuff.
    for pkg in ["ssl", "libcrypto", "zlib", "xml", "mpfr", "lapack", "blas", "f2c"]:
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


def main(args: argparse.Namespace) -> None:
    pyodide_root = get_pyodide_root()
    xbuildenv_path = pyodide_root / "xbuildenv"
    xbuildenv_root = xbuildenv_path / "pyodide-root"
    shutil.rmtree(xbuildenv_path, ignore_errors=True)

    copy_xbuild_files(xbuildenv_path)
    copy_wasm_libs(xbuildenv_path)

    (xbuildenv_root / "package.json").write_text("{}")
    res = subprocess.run(
        ["npm", "i", "node-fetch@2"],
        cwd=xbuildenv_root,
        capture_output=True,
        encoding="utf8",
    )
    if res.returncode != 0:
        logger.error("Failed to install node-fetch:")
        exit_with_stdio(res)

    res = subprocess.run(
        ["pip", "freeze", "--path", get_make_flag("HOSTSITEPACKAGES")],
        capture_output=True,
        encoding="utf8",
    )
    if res.returncode != 0:
        logger.error("Failed to run pip freeze:")
        exit_with_stdio(res)

    (xbuildenv_path / "requirements.txt").write_text(res.stdout)
    (xbuildenv_root / "unisolated.txt").write_text("\n".join(get_unisolated_packages()))
