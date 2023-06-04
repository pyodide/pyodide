import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen, urlretrieve

from .common import exit_with_stdio, get_build_flag
from .create_pypa_index import create_pypa_index
from .logger import logger


def _download_xbuildenv(
    version: str, xbuildenv_path: Path, *, url: str | None = None
) -> None:
    from shutil import rmtree, unpack_archive
    from tempfile import NamedTemporaryFile

    logger.info("Downloading xbuild environment")
    rmtree(xbuildenv_path, ignore_errors=True)

    xbuildenv_url = (
        url
        or f"https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2"
    )
    with NamedTemporaryFile(suffix=".tar") as f:
        urlretrieve(
            xbuildenv_url,
            f.name,
        )
        unpack_archive(f.name, xbuildenv_path)


def install_xbuildenv(version: str, xbuildenv_path: Path) -> None:
    logger.info("Installing xbuild environment")

    xbuildenv_path = xbuildenv_path / "xbuildenv"
    xbuildenv_root = xbuildenv_path / "pyodide-root"

    os.environ["PYODIDE_ROOT"] = str(xbuildenv_root)

    host_site_packages = Path(get_build_flag("HOSTSITEPACKAGES"))
    host_site_packages.mkdir(exist_ok=True, parents=True)
    result = subprocess.run(
        [
            "pip",
            "install",
            "--no-user",
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
    if (repodata_json := xbuildenv_root / "dist" / "repodata.json").exists():
        repodata_bytes = repodata_json.read_bytes()
    else:
        repodata_url = cdn_base + "repodata.json"
        with urlopen(repodata_url) as response:
            repodata_bytes = response.read()
    repodata = json.loads(repodata_bytes)
    version = repodata["info"]["version"]
    create_pypa_index(repodata["packages"], xbuildenv_root, cdn_base)


def install(path: Path, *, download: bool = True, url: str | None = None) -> None:
    """
    Install cross-build environment.

    Parameters
    ----------
    path
        A path to the cross-build environment.
    download
        Whether to download the cross-build environment before installing it.
    url
        URL to download the cross-build environment from. This is only used
        if `download` is True. The URL should point to a tarball containing
        the cross-build environment. If not specified, the corresponding
        release on GitHub is used.

        Warning: if you are downloading from a version that is not the same
        as the current version of pyodide-build, make sure that the cross-build
        environment is compatible with the current version of Pyodide.
    """
    from . import __version__

    version = __version__

    if not download and not path.exists():
        logger.error("xbuild environment not exists")
        raise FileNotFoundError(path)

    if download and path.exists():
        logger.warning("xbuild environment already exists, skipping download")

    elif download:
        _download_xbuildenv(version, path, url=url)

    install_xbuildenv(version, path)
