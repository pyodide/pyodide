import shutil
import subprocess
from pathlib import Path

from .build_env import (
    get_build_flag,
    get_pyodide_root,
    get_unisolated_packages,
)
from .common import exit_with_stdio
from .logger import logger
from .recipe import load_all_recipes


def _copy_xbuild_files(
    pyodide_root: Path, xbuildenv_path: Path, skip_missing_files: bool = False
) -> None:
    site_packages = Path(get_build_flag("HOSTSITEPACKAGES"))
    # Store package cross-build-files into site_packages_extras in the same tree
    # structure as they would appear in the real package.
    # In install_xbuildenv, we will use:
    # pip install -t $HOSTSITEPACKAGES -r requirements.txt
    # cp site-packages-extras $HOSTSITEPACKAGES
    site_packages_extras = xbuildenv_path / "site-packages-extras"
    recipes = load_all_recipes(pyodide_root / "packages")
    for recipe in recipes.values():
        xbuild_files = recipe.build.cross_build_files
        for path in xbuild_files:
            source = site_packages / path
            target = site_packages_extras / path
            target.parent.mkdir(parents=True, exist_ok=True)

            if not source.exists():
                if skip_missing_files:
                    logger.warning(f"Cross-build file '{path}' not found")
                    continue

                raise FileNotFoundError(f"Cross-build file '{path}' not found")

            shutil.copy(source, target)


def _copy_wasm_libs(
    pyodide_root: Path, xbuildenv_root: Path, skip_missing_files: bool = False
) -> None:
    def get_relative_path(pyodide_root: Path, flag: str) -> Path:
        return Path(get_build_flag(flag)).relative_to(pyodide_root)

    pythoninclude = get_relative_path(pyodide_root, "PYTHONINCLUDE")
    sysconfig_dir = get_relative_path(pyodide_root, "SYSCONFIGDATA_DIR")
    # TODO: remove libs from the xbuildenv
    wasm_lib_dir = Path("packages") / ".libs"
    to_copy: list[Path] = [
        pythoninclude,
        sysconfig_dir,
        Path("Makefile.envs"),
        wasm_lib_dir / "cmake",
        Path("dist/pyodide-lock.json"),
        Path("dist/python"),
        Path("dist/python_stdlib.zip"),
        Path("tools/constraints.txt"),
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
        if not (pyodide_root / path).exists():
            if skip_missing_files:
                logger.warning(f"Cross-build file '{path}' not found")
                continue

            raise FileNotFoundError(f"Cross-build file '{path}' not found")

        if (pyodide_root / path).is_dir():
            shutil.copytree(
                pyodide_root / path, xbuildenv_root / path, dirs_exist_ok=True
            )
        else:
            (xbuildenv_root / path).parent.mkdir(exist_ok=True, parents=True)
            shutil.copy(pyodide_root / path, xbuildenv_root / path)


def create(
    path: str | Path,
    pyodide_root: Path | None = None,
    *,
    skip_missing_files: bool = False,
) -> None:
    if pyodide_root is None:
        pyodide_root = get_pyodide_root()

    xbuildenv_path = Path(path) / "xbuildenv"
    xbuildenv_root = xbuildenv_path / "pyodide-root"

    shutil.rmtree(xbuildenv_path, ignore_errors=True)
    xbuildenv_path.mkdir(parents=True, exist_ok=True)
    xbuildenv_root.mkdir()

    _copy_xbuild_files(pyodide_root, xbuildenv_path, skip_missing_files)
    _copy_wasm_libs(pyodide_root, xbuildenv_root, skip_missing_files)

    (xbuildenv_root / "package.json").write_text("{}")
    res = subprocess.run(
        ["pip", "freeze", "--path", get_build_flag("HOSTSITEPACKAGES")],
        capture_output=True,
        encoding="utf8",
    )
    if res.returncode != 0:
        logger.error("Failed to run pip freeze:")
        exit_with_stdio(res)

    (xbuildenv_path / "requirements.txt").write_text(res.stdout)
    (xbuildenv_root / "unisolated.txt").write_text("\n".join(get_unisolated_packages()))
