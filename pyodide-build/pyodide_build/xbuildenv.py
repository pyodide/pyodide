import json
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests
from pyodide_lock import PyodideLockSpec

from . import build_env
from .common import exit_with_stdio
from .create_pypa_index import create_pypa_index
from .logger import logger


class CrossBuildEnvManager:
    """
    Manager for the xbuild environment.
    """
    def __init__(self, env_dir: str | Path) -> None:
        self.env_dir = Path(env_dir).resolve()

        self.env_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_version(self, version: str) -> Path:
        """Returns the path to the xbuildenv for the given version."""
        return self.env_dir / version

    @property
    def _symlink_path(self):
        return self.env_dir / "xbuildenv"

    def list_versions(self, compatible_only: bool = True) -> list[str]:
        """
        List the downloaded xbuildenv versions.
        """
        versions = []
        for version_dir in self.env_dir.glob("*"):
            if not version_dir.is_dir() or str(versions) == str(self._symlink_path):
                continue

            versions.append(version_dir.name)

        return versions

    def use_version(self, version: str) -> None:
        """
        Select the xbuildenv version to use.

        This creates a symlink to the selected version in the xbuildenv directory.

        Parameters
        ----------
        version : str
            The version of xbuildenv to use.
        """
        logger.info(f"Using Pyodide xbuild environment verison: {version}")

        version_path = self._path_for_version(version)
        symlink_path = self._symlink_path

        if symlink_path.exists():
            shutil.rmtree(symlink_path)

        symlink_path.symlink_to(version_path)

    def _download(self, url: str, path: Path) -> None:
        logger.info("Downloading Pyodide xbuild environment")

        if path.exists():
            raise ValueError(f"Path {path} already exists")

        # xbuildenv_url = (
        #     url
        #     or f"https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2"
        # )

        r = requests.get(url)

        if r.status_code != 200:
            raise ValueError(f"Failed to download xbuild environment from {url} (status code: {r.status_code})")

        with NamedTemporaryFile(suffix=".tar") as f:
            Path(f).write_bytes(r.content)
            shutil.unpack_archive(f.name, path)

    def _install(self, path: Path, version: str) -> Path:
        """
        Install the xbuild environment.
        This includes installing packages that are used in the cross-build environment
        and creating the PyPA index for the packages

        Parameters
        ----------
        path
            Path to the xbuildenv directory.
        """
        # TODO: there is an extra directory level in the path, which we can remove
        xbuildenv_root = path / "xbuildenv"
        xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"
        install_marker = path / ".installed"

        if install_marker.exists():
            return xbuildenv_root

        logger.info("Installing Pyodide xbuild environment")

        # TODO: use a separate configuration file for variables that are used only in package building
        # 1. Install the packages that are used in the cross-build environment
        host_site_packages = Path(
            build_env._get_make_environment_vars(pyodide_root=xbuildenv_pyodide_root)[
                "HOSTSITEPACKAGES"
            ]
        )
        host_site_packages.mkdir(exist_ok=True, parents=True)
        result = subprocess.run(
            [
                "pip",
                "install",
                "--no-user",
                "-t",
                host_site_packages,
                "-r",
                xbuildenv_root / "requirements.txt",
            ],
            capture_output=True,
            encoding="utf8",
        )

        if result.returncode != 0:
            exit_with_stdio(result)
        # Copy the site-packages-extras (coming from the cross-build-files meta.yaml
        # key) over the site-packages directory with the newly installed packages.
        shutil.copytree(
            xbuildenv_root / "site-packages-extras", host_site_packages, dirs_exist_ok=True
        )

        # 2. Create the PyPI index for the packages
        self._create_pypi_index(xbuildenv_pyodide_root, version)

        install_marker.touch()

        return xbuildenv_root

    def _create_pypi_index(self, xbuildenv_pyodide_root: Path, version: str):
        """
        Create the PyPI index for the packages in the xbuild environment.
        TODO: Creating the PyPI Index is not critical for the xbuild environment to work, so maybe we should
              move this to a separate command (to pyodide venv?)
        """
        cdn_base = f"https://cdn.jsdelivr.net/pyodide/v{version}/full/"
        lockfile_path = xbuildenv_pyodide_root / "dist" / "pyodide-lock.json"

        if not lockfile_path.exists():
            logger.warning(f"Pyodide lockfile not found at {lockfile_path}. Skipping PyPI index creation")
            return

        lockfile = PyodideLockSpec(**json.loads(lockfile_path.read_bytes()))
        create_pypa_index(lockfile.packages, xbuildenv_pyodide_root, cdn_base)

    def install(self, url: str, version: str | None = None) -> Path:
        """
        Install cross-build environment.

        # TODO: support installing xbuildenv version that is not the same as the current version of pyodide-build

        Parameters
        ----------
        version

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

        Returns
        -------
        Path to the Pyodide root directory for the cross-build environment.
        """

        if not version:
            version = _url_to_version(url)

        path = self._path_for_version(version)

        if path.exists():
            logger.warning("xbuild environment already exists, skipping download")
        else:
            self._download(url, path)

        installed_path = self._install(path, version)
        self.use_version(version)

        return installed_path


def _url_to_version(url: str) -> str:
    return url.replace("://", "_").replace(".", "_").replace("/", "_");











