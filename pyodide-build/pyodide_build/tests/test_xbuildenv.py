import pytest
from pyodide_build.xbuildenv import CrossBuildEnvManager, _url_to_version


class TestCrossBuildEnvManager:
    def test_current_version_dir(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)
        assert manager.current_version_dir == tmp_path / "xbuildenv"

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
        cur_version_dir = manager.current_version_dir

        cur_version_dir.mkdir(exist_ok=True)
        (cur_version_dir / "file").touch()

        (tmp_path / "0.25.0").mkdir()
        (tmp_path / "0.25.0" / "0.25.0_file").touch()

        with pytest.raises(ValueError, match="Cannot find xbuildenv version not_version"):
            manager.use_version("not_version")

        manager.use_version("0.25.0")

        assert cur_version_dir.is_symlink()
        assert cur_version_dir.resolve() == tmp_path / "0.25.0"
        assert (cur_version_dir / "0.25.0_file").exists()
        assert not (cur_version_dir / "file").exists()
    
    def test_delete_version(self, tmp_path):
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

        assert manager.current_version_dir.is_symlink()
        assert manager.current_version_dir.resolve() == tmp_path / "0.25.0"

        with pytest.raises(ValueError, match="Cannot find xbuildenv version not_version"):
            manager.delete_version("not_version")
        
        manager.delete_version("0.25.1")
        assert not manager._path_for_version("0.25.1").exists()

        manager.delete_version("0.25.0")
        assert not manager._path_for_version("0.25.0").exists()
        assert not manager.current_version_dir.exists()

        assert set(manager.list_versions()) == set(versions) - {"0.25.0", "0.25.1"}

    def test_install(self, tmp_path):
        manager = CrossBuildEnvManager(tmp_path)

        version = "0.25.0"
        url = f"
    

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
def test_url_to_version(url: str, version: str):
    assert _url_to_version(url) == version