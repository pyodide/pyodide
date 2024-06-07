import json
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from pyodide_lock import PyodideLockSpec

from . import build_env
from .create_package_index import create_package_index
from .logger import logger

XBUILDENV_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2"
CDN_BASE = "https://cdn.jsdelivr.net/pyodide/v{version}/full/"


class CrossBuildEnvManager:
    """
    Manager for the cross-build environment.
    """

    def __init__(self, env_dir: str | Path) -> None:
        self.env_dir = Path(env_dir).resolve()

        try:
            self.env_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(
                f"Failed to create cross-build environment at {self.env_dir}"
            ) from e

    @property
    def symlink_dir(self):
        """
        Returns the path to the symlink that points to the currently used xbuildenv version.
        """
        return self.env_dir / "xbuildenv"

    @property
    def pyodide_root(self) -> Path:
        """
        Returns the path to the pyodide-root directory inside the xbuildenv directory.
        """
        return self.symlink_dir.resolve() / "xbuildenv" / "pyodide-root"

    @property
    def current_version(self) -> str | None:
        """
        Returns the currently used xbuildenv version.
        """
        if not self.symlink_dir.exists():
            return None

        return self.symlink_dir.resolve().name

    def _path_for_version(self, version: str) -> Path:
        """Returns the path to the xbuildenv for the given version."""
        return self.env_dir / version

    def list_versions(self) -> list[str]:
        """
        List the downloaded xbuildenv versions.

        TODO: add a parameter to list only compatible versions
        """
        versions = []
        for version_dir in self.env_dir.glob("*"):
            if not version_dir.is_dir() or version_dir == self.symlink_dir:
                continue

            versions.append(version_dir.name)

        return sorted(versions)

    def use_version(self, version: str) -> None:
        """
        Select the xbuildenv version to use.

        This creates a symlink to the selected version in the xbuildenv directory.

        Parameters
        ----------
        version
            The version of xbuildenv to use.
        """
        logger.info(f"Using Pyodide cross-build environment version: {version}")

        version_path = self._path_for_version(version)
        if not version_path.exists():
            raise ValueError(
                f"Cannot find cross-build environment version {version}, available versions: {self.list_versions()}"
            )

        symlink_dir = self.symlink_dir

        if symlink_dir.exists():
            if symlink_dir.is_symlink():
                # symlink to a directory, expected case
                symlink_dir.unlink()
            elif symlink_dir.is_dir():
                # real directory, for backwards compatibility
                shutil.rmtree(symlink_dir)
            else:
                # file. This should not happen unless the user manually created a file
                # but we will remove it anyway
                symlink_dir.unlink()

        symlink_dir.symlink_to(version_path)

    def install(
        self,
        version: str | None = None,
        *,
        url: str | None = None,
        skip_install_cross_build_packages: bool = False,
    ) -> Path:
        """
        Install cross-build environment.

        Parameters
        ----------
        version
            The version of the cross-build environment to install. If not specified,
            use the same version as the current version of pyodide-build.
            # TODO: installing the different version is not supported yet
        url
            URL to download the cross-build environment from.
            The URL should point to a tarball containing the cross-build environment.
            This is useful for testing unreleased version of the cross-build environment.

            Warning: if you are downloading from a version that is not the same
            as the current version of pyodide-build, make sure that the cross-build
            environment is compatible with the current version of Pyodide.
        skip_install_cross_build_packages
            If True, skip installing the cross-build packages. This is mostly for testing purposes.

        Returns
        -------
        Path to the root directory for the cross-build environment.
        """

        if url and version:
            raise ValueError("Cannot specify both version and url")

        if url:
            version = _url_to_version(url)
            download_url = url
        else:
            version = version or self._infer_version()
            download_url = self._download_url_for_version(version)

        download_path = self._path_for_version(version)

        if download_path.exists():
            logger.info(
                "The cross-build environment already exists at '%s', skipping download",
                download_path,
            )
        else:
            self._download(download_url, download_path)

        try:
            # there is an redundant directory "xbuildenv" inside the xbuildenv archive
            # TODO: remove the redundant directory from the archive
            xbuildenv_root = download_path / "xbuildenv"
            xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"
            install_marker = download_path / ".installed"
            if not install_marker.exists():
                logger.info("Installing Pyodide cross-build environment")

                if not skip_install_cross_build_packages:
                    self._install_cross_build_packages(
                        xbuildenv_root, xbuildenv_pyodide_root
                    )

                if not url:
                    # If installed from url, skip creating the PyPI index (version is not known)
                    self._create_package_index(xbuildenv_pyodide_root, version)

            install_marker.touch()
            self.use_version(version)
        except Exception as e:
            # if the installation failed, remove the downloaded directory
            shutil.rmtree(download_path)
            raise e

        return xbuildenv_pyodide_root

    def _infer_version(self) -> str:
        from . import __version__

        return __version__

    def _download_url_for_version(self, version: str) -> str:
        return XBUILDENV_URL.format(version=version)

    def _download(self, url: str, path: Path) -> None:
        """
        Download the cross-build environment from the given URL and extract it to the given path.

        Parameters
        ----------
        url
            URL to download the cross-build environment from.
        path
            Path to extract the cross-build environment to.
            If the path already exists, raise an error.
        """
        logger.info("Downloading Pyodide cross-build environment from %s", url)

        if path.exists():
            raise FileExistsError(f"Path {path} already exists")

        try:
            resp = urlopen(url)
            data = resp.read()
        except Exception as e:
            raise ValueError(
                f"Failed to download cross-build environment from {url}"
            ) from e

        # FIXME: requests makes a verbose output (see: https://github.com/pyodide/pyodide/issues/4810)
        # r = requests.get(url)

        # if r.status_code != 200:
        #     raise ValueError(
        #         f"Failed to download cross-build environment from {url} (status code: {r.status_code})"
        #     )

        with NamedTemporaryFile(suffix=".tar") as f:
            f_path = Path(f.name)
            f_path.write_bytes(data)
            shutil.unpack_archive(str(f_path), path)

    def _install_cross_build_packages(
        self, xbuildenv_root: Path, xbuildenv_pyodide_root: Path
    ) -> None:
        """
        Install package that are used in the cross-build environment.

        Parameters
        ----------
        xbuildenv_root
            Path to the xbuildenv directory.
        xbuildenv_pyodide_root
            Path to the pyodide-root directory inside the xbuildenv directory.
        """
        host_site_packages = self._host_site_packages_dir(xbuildenv_pyodide_root)
        host_site_packages.mkdir(exist_ok=True, parents=True)
        result = subprocess.run(
            [
                "pip",
                "install",
                "--no-user",
                "-t",
                str(host_site_packages),
                "-r",
                str(xbuildenv_root / "requirements.txt"),
            ],
            capture_output=True,
            encoding="utf8",
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to install cross-build packages: {result.stderr}"
            )

        # Copy the site-packages-extras (coming from the cross-build-files meta.yaml
        # key) over the site-packages directory with the newly installed packages.
        shutil.copytree(
            xbuildenv_root / "site-packages-extras",
            host_site_packages,
            dirs_exist_ok=True,
        )

    def _host_site_packages_dir(
        self, xbuildenv_pyodide_root: Path | None = None
    ) -> Path:
        """
        Returns the path to the hostsitepackages directory in the xbuild environment.
        This is inferred using the current version of the xbuild environment,
        but can optionally be overridden by passing the pyodide root directory as a parameter.

        Parameters
        ----------
        xbuildenv_pyodide_root
            The path to the pyodide root directory inside the xbuild environment.
        """

        if xbuildenv_pyodide_root is None:
            xbuildenv_pyodide_root = self.pyodide_root

        return Path(
            build_env.get_build_environment_vars(pyodide_root=xbuildenv_pyodide_root)[
                "HOSTSITEPACKAGES"
            ]
        )

    def _create_package_index(self, xbuildenv_pyodide_root: Path, version: str) -> None:
        """
        Create the PyPI index for the packages in the xbuild environment.
        TODO: Creating the PyPI Index is not required for the xbuild environment to work, so maybe we can
              move this to a separate command (to pyodide venv?)
        """

        cdn_base = CDN_BASE.format(version=version)
        lockfile_path = xbuildenv_pyodide_root / "dist" / "pyodide-lock.json"

        if not lockfile_path.exists():
            logger.warning(
                f"Pyodide lockfile not found at {lockfile_path}. Skipping PyPI index creation"
            )
            return

        lockfile = PyodideLockSpec(**json.loads(lockfile_path.read_bytes()))
        create_package_index(lockfile.packages, xbuildenv_pyodide_root, cdn_base)

    def uninstall_version(self, version: str) -> None:
        """
        Uninstall the installed xbuildenv version.

        Parameters
        ----------
        version
            The version of xbuildenv to uninstall.
        """
        version_path = self._path_for_version(version)

        # if the target version is the current version, remove the symlink
        # to prevent symlinking to a non-existent directory
        if self.symlink_dir.resolve() == version_path:
            self.symlink_dir.unlink()

        if version_path.is_dir():
            shutil.rmtree(version_path)
        else:
            raise ValueError(
                f"Cannot find cross-build environment version {version}, available versions: {self.list_versions()}"
            )


def _url_to_version(url: str) -> str:
    return url.replace("://", "_").replace(".", "_").replace("/", "_")
