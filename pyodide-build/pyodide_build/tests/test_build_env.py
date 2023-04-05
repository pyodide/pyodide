import os

import pytest

from conftest import ROOT_PATH
from pyodide_build import build_env


@pytest.fixture(scope="function", autouse=True)
def reset_env_vars():
    # Will reset the environment variables to their original values after each test.

    old_environ = dict(os.environ)

    yield

    os.environ.clear()
    os.environ.update(old_environ)


@pytest.fixture(scope="function", autouse=True)
def reset_cache():
    # Will remove all caches before each test.

    build_env.get_pyodide_root.cache_clear()
    build_env.get_build_environment_vars.cache_clear()

    yield


class TestInTree:
    def test_init_environment(self):
        assert "PYODIDE_ROOT" not in os.environ

        build_env.init_environment()

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(ROOT_PATH)

    def test_init_environment_pyodide_root_already_set(self):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        build_env.init_environment()

        assert os.environ["PYODIDE_ROOT"] == "/set_by_user"

    def test_get_pyodide_root(self):
        assert "PYODIDE_ROOT" not in os.environ

        assert build_env.get_pyodide_root() == ROOT_PATH

    def test_get_pyodide_root_pyodide_root_already_set(self):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        assert str(build_env.get_pyodide_root()) == "/set_by_user"

    def test_search_pyodide_root(self, tmp_path):
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[tool.pyodide]")
        assert build_env.search_pyodide_root(tmp_path) == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir") == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir" / "subdir") == tmp_path

        pyproject_file.unlink()
        with pytest.raises(FileNotFoundError):
            build_env.search_pyodide_root(tmp_path)

    def test_in_xbuildenv(self):
        assert not build_env.in_xbuildenv()

    def test_get_build_environment_vars(self):
        build_vars = build_env.get_build_environment_vars()

        for var in build_env.BUILD_VARS:
            assert var in build_vars, f"Missing {var}"

        # Additionally we set these variables
        for var in [
            "PYODIDE",
            "PKG_CONFIG_PATH",
            "CMAKE_TOOLCHAIN_FILE",
            "PYO3_CONFIG_FILE",
        ]:
            assert var in build_vars, f"Missing {var}"

    def test_get_build_flag(self):
        for var in build_env.BUILD_VARS:
            assert (
                build_env.get_build_flag(var)
                == build_env.get_build_environment_vars()[var]
            )

        with pytest.raises(ValueError):
            build_env.get_build_flag("UNKNOWN_VAR")


class TestOutOfTree(TestInTree):
    @pytest.fixture(scope="function", autouse=True)
    def xbuildenv(self, selenium):
        # TODO: selenium fixture is a hack to make these tests run only after building Pyodide.
        # TODO: Requires: https://github.com/pyodide/pyodide/pull/3732
        pass

    pass
