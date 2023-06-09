# This file contains tests that ensure build environment is properly initialized in
# both in-tree and out-of-tree builds.

# TODO: move functions that are tested here to a separate module

import os
from pathlib import Path

import pytest

from conftest import ROOT_PATH
from pyodide_build import common


@pytest.fixture(scope="function")
def reset_env_vars():
    # Will reset the environment variables to their original values after each test.

    os.environ.pop("PYODIDE_ROOT", None)
    os.environ.pop("__LOADED_PYODIDE_ENV", None)
    old_environ = dict(os.environ)

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


@pytest.fixture(scope="function")
def reset_cache():
    # Will remove all caches before each test.

    common.get_pyodide_root.cache_clear()
    common.get_build_environment_vars.cache_clear()
    common.get_unisolated_packages.cache_clear()

    yield


class TestInTree:
    def test_init_environment(self, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        common.init_environment()

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(ROOT_PATH)

    def test_init_environment_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        common.init_environment()

        assert os.environ["PYODIDE_ROOT"] == "/set_by_user"

    def test_get_pyodide_root(self, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        assert common.get_pyodide_root() == ROOT_PATH

    def test_get_pyodide_root_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        assert str(common.get_pyodide_root()) == "/set_by_user"

    def test_search_pyodide_root(self, tmp_path, reset_env_vars, reset_cache):
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[tool.pyodide]")
        assert common.search_pyodide_root(tmp_path) == tmp_path
        assert common.search_pyodide_root(tmp_path / "subdir") == tmp_path
        assert common.search_pyodide_root(tmp_path / "subdir" / "subdir") == tmp_path

        pyproject_file.unlink()
        with pytest.raises(FileNotFoundError):
            common.search_pyodide_root(tmp_path)

    def test_in_xbuildenv(self, reset_env_vars, reset_cache):
        assert not common.in_xbuildenv()

    def test_get_build_environment_vars(self, reset_env_vars, reset_cache):
        build_vars = common.get_build_environment_vars()
        extra_vars = set(
            ["PYODIDE", "PKG_CONFIG_PATH", "CMAKE_TOOLCHAIN_FILE", "PYO3_CONFIG_FILE"]
        )

        for var in build_vars:
            assert var in common.BUILD_VARS | extra_vars, f"Unknown {var}"

        # Additionally we set these variables
        for var in extra_vars:
            assert var in build_vars, f"Missing {var}"

    def test_get_build_flag(self, reset_env_vars, reset_cache):
        for key, val in common.get_build_environment_vars().items():
            assert common.get_build_flag(key) == val

        with pytest.raises(ValueError):
            common.get_build_flag("UNKNOWN_VAR")


class TestOutOfTree(TestInTree):
    # TODO: selenium fixture is a hack to make these tests run only after building Pyodide.
    @pytest.fixture(scope="function", autouse=True)
    def xbuildenv(self, selenium, tmp_path, reset_env_vars, reset_cache):
        import subprocess as sp

        assert "PYODIDE_ROOT" not in os.environ

        envpath = Path(tmp_path) / ".pyodide-xbuildenv"
        result = sp.run(
            [
                "pyodide",
                "xbuildenv",
                "create",
                str(envpath),
                "--root",
                ROOT_PATH,
                "--skip-missing-files",
            ]
        )

        assert result.returncode == 0

        yield tmp_path

    @pytest.fixture(scope="function", autouse=True)
    def chdir_xbuildenv(self, xbuildenv):
        cur_dir = os.getcwd()

        os.chdir(xbuildenv)

        try:
            yield
        finally:
            os.chdir(cur_dir)

    # Note: other tests are inherited from TestInTree

    def test_init_environment(self, xbuildenv, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        common.init_environment()

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(
            xbuildenv / ".pyodide-xbuildenv/xbuildenv/pyodide-root"
        )

    def test_get_pyodide_root(self, xbuildenv, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        assert (
            common.get_pyodide_root()
            == xbuildenv / ".pyodide-xbuildenv/xbuildenv/pyodide-root"
        )

    def test_in_xbuildenv(self, reset_env_vars, reset_cache):
        assert common.in_xbuildenv()
