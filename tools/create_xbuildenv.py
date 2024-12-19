import argparse
import logging
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

try:
    from pyodide_build.build_env import (
        get_build_flag,
        get_unisolated_packages,
    )
    from pyodide_build.recipe import load_all_recipes
except ImportError:
    print("Requires pyodide-build package to be installed")
    sys.exit(1)


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
                    logging.warning(f"Cross-build file '{path}' not found")
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

    to_copy: list[Path] = [
        pythoninclude,
        sysconfig_dir,
        Path("Makefile.envs"),
        Path("dist/pyodide-lock.json"),
        Path("dist/python"),
        Path("dist/python_stdlib.zip"),
        Path("tools/constraints.txt"),
    ]
    to_copy.extend(
        x.relative_to(pyodide_root) for x in (pyodide_root / "dist").glob("pyodide.*")
    )

    for path in to_copy:
        if not (pyodide_root / path).exists():
            if skip_missing_files:
                logging.warning(f"Cross-build file '{path}' not found")
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
    pyodide_root: Path,
    *,
    skip_missing_files: bool = False,
) -> None:
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
        check=False,
    )
    if res.returncode != 0:
        logging.error("Failed to run pip freeze:")
        if res.stdout:
            logging.error("  stdout:")
            logging.error(textwrap.indent(res.stdout, "    "))
        if res.stderr:
            logging.error("  stderr:")
            logging.error(textwrap.indent(res.stderr, "    "))
        sys.exit(1)

    (xbuildenv_path / "requirements.txt").write_text(res.stdout)
    (xbuildenv_root / "unisolated.txt").write_text("\n".join(get_unisolated_packages()))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create cross-build environment for building packages for Pyodide."
    )
    parser.add_argument("path", help="path to cross-build environment directory")
    parser.add_argument(
        "--skip-missing-files",
        action="store_true",
        help="skip if cross build files are missing instead of raising an error. This is useful for testing.",
    )

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    root = Path(__file__).parent.parent

    create(args.path, pyodide_root=root, skip_missing_files=args.skip_missing_files)

    print(f"Pyodide cross-build environment created at {args.path}")


if __name__ == "__main__":
    main()
