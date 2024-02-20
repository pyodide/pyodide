import os
import shutil
from pathlib import Path

import pytest
from pyodide_lock import PyodideLockSpec

from conftest import ROOT_PATH
from pyodide_build import build_env
from pyodide_build.common import chdir, xbuildenv_dirname


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


def mock_pyodide_lock() -> PyodideLockSpec:
    return PyodideLockSpec(
        info={
            "version": "0.22.1",
            "arch": "wasm32",
            "platform": "emscripten_xxx",
            "python": "3.11",
        },
        packages={},
    )


@pytest.fixture(scope="module")
def temp_xbuildenv(tmp_path_factory):
    """
    Create a temporary xbuildenv archive
    """
    base = tmp_path_factory.mktemp("base")

    path = Path(base)

    xbuildenv = path / "xbuildenv"
    xbuildenv.mkdir()

    pyodide_root = xbuildenv / "pyodide-root"
    site_packages_extra = xbuildenv / "site-packages-extras"
    requirements_txt = xbuildenv / "requirements.txt"

    pyodide_root.mkdir()
    site_packages_extra.mkdir()
    requirements_txt.touch()

    (pyodide_root / "Makefile.envs").write_text(
        """
export HOSTSITEPACKAGES=$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages

.output_vars:
	set
"""  # noqa: W191
    )
    (pyodide_root / "dist").mkdir()
    mock_pyodide_lock().to_json(pyodide_root / "dist" / "pyodide-lock.json")

    with chdir(base):
        archive_name = shutil.make_archive("xbuildenv", "tar")

    yield base, archive_name


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

    cur_dir = os.getcwd()

    os.chdir(tmp_path)

    try:
        yield tmp_path
    finally:
        os.chdir(cur_dir)
