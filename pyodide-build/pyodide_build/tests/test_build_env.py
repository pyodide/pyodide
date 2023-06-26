# This file contains tests that ensure build environment is properly initialized in
# both in-tree and out-of-tree builds.

# TODO: move functions that are tested here to a separate module

import os
from pathlib import Path

import pytest

from conftest import ROOT_PATH
from pyodide_build import build_env, common


@pytest.fixture(scope="function")
def reset_env_vars():
    # Will reset the environment variables to their original values after each test.

    os.environ.pop("PYODIDE_ROOT", None)
    old_environ = dict(os.environ)

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


@pytest.fixture(scope="function")
def reset_cache():
    # Will remove all caches before each test.

    build_env.get_pyodide_root.cache_clear()
    build_env.get_build_environment_vars.cache_clear()
    build_env.get_unisolated_packages.cache_clear()

    yield


class TestInTree:
    def test_init_environment(self, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        build_env.init_environment()

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(ROOT_PATH)

    def test_init_environment_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        build_env.init_environment()

        assert os.environ["PYODIDE_ROOT"] == "/set_by_user"

    def test_get_pyodide_root(self, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        assert build_env.get_pyodide_root() == ROOT_PATH

    def test_get_pyodide_root_pyodide_root_already_set(
        self, reset_env_vars, reset_cache
    ):
        assert "PYODIDE_ROOT" not in os.environ
        os.environ["PYODIDE_ROOT"] = "/set_by_user"

        assert str(build_env.get_pyodide_root()) == "/set_by_user"

    def test_search_pyodide_root(self, tmp_path, reset_env_vars, reset_cache):
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text("[tool.pyodide]")
        assert build_env.search_pyodide_root(tmp_path) == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir") == tmp_path
        assert build_env.search_pyodide_root(tmp_path / "subdir" / "subdir") == tmp_path

        pyproject_file.unlink()
        with pytest.raises(FileNotFoundError):
            build_env.search_pyodide_root(tmp_path)

    def test_in_xbuildenv(self, reset_env_vars, reset_cache):
        assert not build_env.in_xbuildenv()

    def test_get_build_environment_vars(self, reset_env_vars, reset_cache):
        build_vars = build_env.get_build_environment_vars()
        extra_vars = set(
            ["PYODIDE", "PKG_CONFIG_PATH", "CMAKE_TOOLCHAIN_FILE", "PYO3_CONFIG_FILE"]
        )

        for var in build_vars:
            assert var in build_env.BUILD_VARS | extra_vars, f"Unknown {var}"

        # Additionally we set these variables
        for var in extra_vars:
            assert var in build_vars, f"Missing {var}"

    def test_get_build_flag(self, reset_env_vars, reset_cache):
        for key, val in build_env.get_build_environment_vars().items():
            assert build_env.get_build_flag(key) == val

        with pytest.raises(ValueError):
            build_env.get_build_flag("UNKNOWN_VAR")

    def test_get_build_environment_vars_host_env(
        self, monkeypatch, reset_env_vars, reset_cache
    ):
        # host environment variables should have precedence over
        # variables defined in Makefile.envs

        import os

        e = build_env.get_build_environment_vars()
        assert e["PYODIDE"] == "1"

        monkeypatch.setenv("HOME", "/home/user")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        monkeypatch.setenv("PKG_CONFIG_PATH", "/x/y/z:/c/d/e")

        build_env.get_build_environment_vars.cache_clear()

        e_host = build_env.get_build_environment_vars()
        assert e_host.get("HOME") == os.environ.get("HOME")
        assert e_host.get("PATH") == os.environ.get("PATH")
        assert e_host["PKG_CONFIG_PATH"].endswith("/x/y/z:/c/d/e")

        assert e_host.get("HOME") != e.get("HOME")
        assert e_host.get("PATH") != e.get("PATH")
        assert e_host.get("PKG_CONFIG_PATH") != e.get("PKG_CONFIG_PATH")

        build_env.get_build_environment_vars.cache_clear()

        monkeypatch.delenv("HOME")
        monkeypatch.setenv("RANDOM_ENV", "1234")

        build_env.get_build_environment_vars.cache_clear()
        e = build_env.get_build_environment_vars()
        assert "HOME" not in e
        assert "RANDOM_ENV" not in e


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

        build_env.init_environment()

        assert "PYODIDE_ROOT" in os.environ
        assert os.environ["PYODIDE_ROOT"] == str(
            xbuildenv / ".pyodide-xbuildenv/xbuildenv/pyodide-root"
        )

    def test_get_pyodide_root(self, xbuildenv, reset_env_vars, reset_cache):
        assert "PYODIDE_ROOT" not in os.environ

        assert (
            build_env.get_pyodide_root()
            == xbuildenv / ".pyodide-xbuildenv/xbuildenv/pyodide-root"
        )

    def test_in_xbuildenv(self, reset_env_vars, reset_cache):
        assert build_env.in_xbuildenv()


def test_check_emscripten_version(monkeypatch):
    s = None

    def get_emscripten_version_info():
        nonlocal s
        return s

    needed_version = build_env.emscripten_version()
    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", get_emscripten_version_info
    )
    s = """\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 3.1.4 (14cd48e6ead13b02a79f47df1a252abc501a3269)
clang version 15.0.0 (https://github.com/llvm/llvm-project ce5588fdf478b6af724977c11a405685cebc3d26)
Target: wasm32-unknown-emscripten
Thread model: posix
"""
    with pytest.raises(
        RuntimeError,
        match=f"Incorrect Emscripten version 3.1.4. Need Emscripten version {needed_version}",
    ):
        build_env.check_emscripten_version()

    s = """\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 1.39.20
clang version 12.0.0 (/b/s/w/ir/cache/git/chromium.googlesource.com-external-github.com-llvm-llvm--project 55fa315b0352b63454206600d6803fafacb42d5e)
"""

    with pytest.raises(
        RuntimeError,
        match=f"Incorrect Emscripten version 1.39.20. Need Emscripten version {needed_version}",
    ):
        build_env.check_emscripten_version()

    s = f"""\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) {build_env.emscripten_version()} (4343cbec72b7db283ea3bda1adc6cb1811ae9a73)
clang version 15.0.0 (https://github.com/llvm/llvm-project 7effcbda49ba32991b8955821b8fdbd4f8f303e2)
"""
    build_env.check_emscripten_version()

    def get_emscripten_version_info():  # type: ignore[no-redef]
        raise FileNotFoundError()

    monkeypatch.setattr(
        build_env, "get_emscripten_version_info", get_emscripten_version_info
    )

    with pytest.raises(
        RuntimeError,
        match=f"No Emscripten compiler found. Need Emscripten version {needed_version}",
    ):
        build_env.check_emscripten_version()


def test_wheel_paths():
    from pathlib import Path

    old_version = "cp38"
    PYMAJOR = int(build_env.get_build_flag("PYMAJOR"))
    PYMINOR = int(build_env.get_build_flag("PYMINOR"))
    PLATFORM = build_env.platform()
    current_version = f"cp{PYMAJOR}{PYMINOR}"
    future_version = f"cp{PYMAJOR}{PYMINOR + 1}"
    strings = []

    for interp in [
        old_version,
        current_version,
        future_version,
        "py3",
        "py2",
        "py2.py3",
    ]:
        for abi in [interp, "abi3", "none"]:
            for arch in [PLATFORM, "linux_x86_64", "any"]:
                strings.append(f"wrapt-1.13.3-{interp}-{abi}-{arch}.whl")

    paths = [Path(x) for x in strings]
    assert [
        x.stem.split("-", 2)[-1]
        for x in common.find_matching_wheels(paths, build_env.pyodide_tags())
    ] == [
        f"{current_version}-{current_version}-{PLATFORM}",
        f"{current_version}-abi3-{PLATFORM}",
        f"{current_version}-none-{PLATFORM}",
        f"{old_version}-abi3-{PLATFORM}",
        f"py3-none-{PLATFORM}",
        f"py2.py3-none-{PLATFORM}",
        "py3-none-any",
        "py2.py3-none-any",
        f"{current_version}-none-any",
    ]
