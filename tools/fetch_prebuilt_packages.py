#!/usr/bin/env python3
"""Reuse the package set of a previous Pyodide release instead of building it.

This is meant for patch releases that do not change the Emscripten version, the
CPython build or any recipe, so that the packages of the previous release are
ABI-compatible and can be shipped as-is. It:

1. downloads ``pyodide-<version>.tar.bz2`` from the GitHub release and copies the
   package files and ``pyodide-lock.json`` into ``dist/``, leaving the freshly
   built core runtime files (``pyodide.asm.*``, ``python_stdlib.zip``, ...)
   untouched,
2. patches ``info.version`` in the lockfile to the current ``PYODIDE_VERSION``
   (``loadPyodide`` refuses lockfiles with a mismatched version),
3. downloads ``xbuildenv-<version>.tar.bz2`` and restores the host site-packages
   (``HOSTSITEPACKAGES``) from it, so that ``tools/create_xbuildenv.py`` finds
   the cross-build files that a real package build would have installed there.

Requires pyodide-build to be installed (``make pyodide_build``).
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

try:
    from pyodide_build.build_env import get_build_flag
except ImportError:
    print("Requires pyodide-build package to be installed")
    sys.exit(1)

RELEASE_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/{name}"

logger = logging.getLogger(__name__)


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        logger.info("Using cached %s", dest)
        return dest
    logger.info("Downloading %s", url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    return dest


def extract(archive: Path, dest: Path) -> None:
    logger.info("Extracting %s", archive.name)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")


def install_packages(prebuilt_dist: Path, dist: Path, new_version: str) -> None:
    lockfile_path = prebuilt_dist / "pyodide-lock.json"
    lockfile = json.loads(lockfile_path.read_text())
    old_version = lockfile["info"]["version"]

    # Files referenced by the lockfile always come from the previous release, even
    # if the core build produced a file of the same name (e.g. micropip), so that
    # the sha256 checksums in the lockfile stay valid.
    package_files = {pkg["file_name"] for pkg in lockfile["packages"].values()}
    for name in sorted(package_files):
        shutil.copy(prebuilt_dist / name, dist / name)
    logger.info(
        "Copied %d package files from Pyodide %s", len(package_files), old_version
    )

    # Everything else (e.g. package .metadata files) is only copied if the core
    # build did not already produce it.
    for path in prebuilt_dist.iterdir():
        if path.name in package_files or path.name == "pyodide-lock.json":
            continue
        if (dist / path.name).exists():
            continue
        if path.is_dir():
            shutil.copytree(path, dist / path.name)
        else:
            shutil.copy(path, dist / path.name)

    lockfile["info"]["version"] = new_version
    (dist / "pyodide-lock.json").write_text(json.dumps(lockfile, indent=1) + "\n")
    logger.info("Installed lockfile (version %s -> %s)", old_version, new_version)


def install_host_site_packages(prebuilt_xbuildenv: Path) -> None:
    host_site_packages = Path(get_build_flag("HOSTSITEPACKAGES"))
    host_site_packages.mkdir(parents=True, exist_ok=True)

    requirements = prebuilt_xbuildenv / "requirements.txt"
    if requirements.read_text().strip():
        logger.info("Installing host packages into %s", host_site_packages)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(host_site_packages),
                "-r",
                str(requirements),
            ],
            check=True,
        )

    extras = prebuilt_xbuildenv / "site-packages-extras"
    if extras.exists():
        logger.info("Copying cross-build files into %s", host_site_packages)
        shutil.copytree(extras, host_site_packages, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="Pyodide release to take the packages from")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "pyodide-prebuilt",
        help="where to store the downloaded release archives",
    )
    parser.add_argument(
        "--skip-host-site-packages",
        action="store_true",
        help="do not restore HOSTSITEPACKAGES from the xbuildenv archive",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pyodide_root = Path(__file__).parent.parent
    dist = pyodide_root / "dist"
    new_version = get_build_flag("PYODIDE_VERSION")
    if not (dist / "pyodide.asm.wasm").exists():
        sys.exit(f"{dist} does not contain a Pyodide core build")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        name = f"pyodide-{args.version}.tar.bz2"
        archive = download(
            RELEASE_URL.format(version=args.version, name=name), args.cache_dir / name
        )
        extract(archive, tmpdir)
        install_packages(tmpdir / "pyodide", dist, new_version)

        if not args.skip_host_site_packages:
            name = f"xbuildenv-{args.version}.tar.bz2"
            archive = download(
                RELEASE_URL.format(version=args.version, name=name),
                args.cache_dir / name,
            )
            extract(archive, tmpdir)
            install_host_site_packages(tmpdir / "xbuildenv")

    print(f"Installed packages from Pyodide {args.version} into {dist}")


if __name__ == "__main__":
    main()
