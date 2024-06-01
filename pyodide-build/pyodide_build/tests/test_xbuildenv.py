# flake8: noqa

import pytest

from pyodide_build.xbuildenv import CrossBuildEnvManager, _url_to_version

from .fixture import (
    dummy_xbuildenv_url,
    fake_xbuildenv_releases_compatible,
    fake_xbuildenv_releases_incompatible,
)


@pytest.fixture()
def monkeypatch_subprocess_run_pip(monkeypatch):
    import subprocess

    called_with = []
    orig_run = subprocess.run

    def monkeypatch_func(cmds, *args, **kwargs):
        if cmds[0] == "pip":
            called_with.extend(cmds)
            return subprocess.CompletedProcess(cmds, 0, "", "")
        else:
            return orig_run(cmds, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", monkeypatch_func)
    yield called_with


class TestCrossBuildEnvManager:
    def test_symlink_dir(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)
        assert manager.symlink_dir == tmp_path / "xbuildenv"

    def test_list_versions(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        versions = [
            "0.25.0",
            "0.25.0dev0",
            "0.25.1",
            "0.26.0a1",
            "0.26.0a2",
            _url_to_version("https://github.com/url/xbuildenv-0.26.0a3.tar.bz2"),
        ]

        for version in versions:
            (tmp_path / version).mkdir()

        (tmp_path / "xbuildenv").mkdir()
        (tmp_path / "not_version").touch()

        assert set(manager.list_versions()) == set(versions)

    def test_use_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)
        cur_version_dir = manager.symlink_dir

        cur_version_dir.mkdir(exist_ok=True)
        (cur_version_dir / "file").touch()

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.25.0" / "0.25.0_file").touch()

        with pytest.raises(
            ValueError, match="Cannot find cross-build environment version not_version"
        ):
            manager.use_version("not_version")

        manager.use_version("0.25.0")

        assert cur_version_dir.is_symlink()
        assert cur_version_dir.resolve() == tmp_path / "0.25.0"
        assert (cur_version_dir / "0.25.0_file").exists()
        assert not (cur_version_dir / "file").exists()

    def test_current_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        assert manager.current_version is None

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.26.0").mkdir()

        manager.use_version("0.25.0")
        assert manager.current_version == "0.25.0"

        manager.use_version("0.26.0")
        assert manager.current_version == "0.26.0"

        manager.uninstall_version("0.26.0")
        assert manager.current_version is None

        manager.use_version("0.25.0")
        assert manager.current_version == "0.25.0"

    def test_download(self, tmp_path, dummy_xbuildenv_url):
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        manager._download(dummy_xbuildenv_url, download_path)

        assert download_path.exists()
        assert (download_path / "xbuildenv").exists()
        assert (download_path / "xbuildenv" / "pyodide-root").exists()

    def test_download_path_exists(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        download_path.mkdir()

        with pytest.raises(FileExistsError, match="Path .* already exists"):
            manager._download(
                "https://example.com/xbuildenv-0.25.0.tar.bz2", download_path
            )

    def test_find_latest_version(self, tmp_path, fake_xbuildenv_releases_compatible):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        latest_version = manager._find_latest_version()
        assert latest_version == "0.2.0", latest_version

    def test_find_latest_version_incompat(
        self, tmp_path, fake_xbuildenv_releases_incompatible
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_incompatible)
        )

        with pytest.raises(
            ValueError, match="No compatible cross-build environment found"
        ):
            manager._find_latest_version()

    def test_install_version(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_compatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_compatible)
        )
        version = "0.1.0"

        manager.install(version)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / version
        assert (manager.symlink_dir / "xbuildenv").exists()
        assert (manager.symlink_dir / "xbuildenv" / "pyodide-root").exists()
        assert (
            manager.symlink_dir / "xbuildenv" / "pyodide-root" / "package_index"
        ).exists()
        assert (manager.symlink_dir / "xbuildenv" / "site-packages-extras").exists()

        # installing the same version again should be a no-op
        manager.install(version)

    def test_install_url(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch, monkeypatch_subprocess_run_pip
    ):
        manager = CrossBuildEnvManager(tmp_path)

        manager.install(version=None, url=dummy_xbuildenv_url)
        version = _url_to_version(dummy_xbuildenv_url)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / version
        assert (manager.symlink_dir / "xbuildenv").exists()
        assert (manager.symlink_dir / "xbuildenv" / "pyodide-root").exists()
        assert not (
            manager.symlink_dir / "xbuildenv" / "pyodide-root" / "package_index"
        ).exists()
        assert (manager.symlink_dir / "xbuildenv" / "site-packages-extras").exists()

    def test_install_force(
        self,
        tmp_path,
        dummy_xbuildenv_url,
        monkeypatch,
        monkeypatch_subprocess_run_pip,
        fake_xbuildenv_releases_incompatible,
    ):
        manager = CrossBuildEnvManager(
            tmp_path, str(fake_xbuildenv_releases_incompatible)
        )
        version = "0.1.0"

        with pytest.raises(
            ValueError,
            match=f"Version {version} is not compatible with the current environment",
        ):
            manager.install(version)

        manager.install(version, force_install=True)

        assert (tmp_path / version).exists()
        assert (tmp_path / version / ".installed").exists()
        assert manager.current_version == version

    def test_install_cross_build_packages(
        self, tmp_path, dummy_xbuildenv_url, monkeypatch_subprocess_run_pip
    ):
        pip_called_with = monkeypatch_subprocess_run_pip
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        manager._download(dummy_xbuildenv_url, download_path)

        xbuildenv_root = download_path / "xbuildenv"
        xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"
        manager._install_cross_build_packages(xbuildenv_root, xbuildenv_pyodide_root)

        assert len(pip_called_with) == 7
        assert pip_called_with[0:4] == ["pip", "install", "--no-user", "-t"]
        assert pip_called_with[4].startswith(
            str(xbuildenv_pyodide_root)
        )  # hostsitepackages
        assert pip_called_with[5:7] == ["-r", str(xbuildenv_root / "requirements.txt")]

        hostsitepackages = manager._host_site_packages_dir(xbuildenv_pyodide_root)
        assert hostsitepackages.exists()

        cross_build_files = xbuildenv_root / "site-packages-extras"
        for file in cross_build_files.iterdir():
            assert (hostsitepackages / file.name).exists()

    def test_create_package_index(self, tmp_path, dummy_xbuildenv_url):
        manager = CrossBuildEnvManager(tmp_path)

        download_path = tmp_path / "test"
        manager._download(dummy_xbuildenv_url, download_path)

        xbuildenv_root = download_path / "xbuildenv"
        xbuildenv_pyodide_root = xbuildenv_root / "pyodide-root"

        manager._create_package_index(xbuildenv_pyodide_root, version="0.25.0")
        (xbuildenv_pyodide_root / "package_index").exists()

    def test_uninstall_version(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        versions = [
            "0.25.0",
            "0.25.0dev0",
            "0.25.1",
            "0.26.0a1",
            "0.26.0a2",
            _url_to_version("https://github.com/url/xbuildenv-0.26.0a3.tar.bz2"),
        ]

        for version in versions:
            (tmp_path / version).mkdir()

        manager.use_version("0.25.0")

        assert manager.symlink_dir.is_symlink()
        assert manager.symlink_dir.resolve() == tmp_path / "0.25.0"

        with pytest.raises(
            ValueError, match="Cannot find cross-build environment version not_version"
        ):
            manager.uninstall_version("not_version")

        manager.uninstall_version("0.25.1")
        assert not manager._path_for_version("0.25.1").exists()

        manager.uninstall_version("0.25.0")
        assert not manager._path_for_version("0.25.0").exists()
        assert not manager.symlink_dir.exists()

        assert set(manager.list_versions()) == set(versions) - {"0.25.0", "0.25.1"}


@pytest.mark.parametrize(
    "url, version",
    [
        (
            "https://example.com/xbuildenv-0.25.0.tar.bz2",
            "https_example_com_xbuildenv-0_25_0_tar_bz2",
        ),
        (
            "http://example.com/subdir/subsubdir/xbuildenv-0.25.0dev0.tar.gz2",
            "http_example_com_subdir_subsubdir_xbuildenv-0_25_0dev0_tar_gz2",
        ),
    ],
)
def test_url_to_version(url: str, version: str) -> None:
    assert _url_to_version(url) == version
