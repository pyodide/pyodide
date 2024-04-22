import os
from pathlib import Path

import pytest

from conftest import ROOT_PATH
from pyodide_build import build_env
from pyodide_build.common import xbuildenv_dirname


@pytest.fixture(scope="module")
def temp_python_lib(tmp_path_factory):
    libdir = tmp_path_factory.mktemp("python")

    path = Path(libdir)

    (path / "test").mkdir()
    (path / "test" / "test_blah.py").touch()
    (path / "turtle.py").touch()

    (path / "module1.py").touch()
    (path / "module2.py").touch()

    (path / "hello_pyodide.py").write_text("def hello(): return 'hello'")

    yield libdir


@pytest.fixture(scope="module")
def temp_python_lib2(tmp_path_factory):
    libdir = tmp_path_factory.mktemp("python")

    path = Path(libdir)

    (path / "module3.py").touch()
    (path / "module4.py").touch()

    (path / "bye_pyodide.py").write_text("def bye(): return 'bye'")

    yield libdir


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


@pytest.fixture(scope="function")
def xbuildenv(selenium, tmp_path, reset_env_vars, reset_cache):
    import subprocess as sp

    assert "PYODIDE_ROOT" not in os.environ

    envpath = Path(tmp_path) / xbuildenv_dirname()
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

    version_dir = envpath / "temp_version"
    version_dir.mkdir()

    sp.run(
        [
            "mv",
            str(envpath / "xbuildenv"),
            str(version_dir),
        ]
    )

    sp.run(
        [
            "ln",
            "-s",
            str(version_dir),
            str(envpath / "xbuildenv"),
        ]
    )

    cur_dir = os.getcwd()

    os.chdir(tmp_path)

    try:
        yield tmp_path
    finally:
        os.chdir(cur_dir)
