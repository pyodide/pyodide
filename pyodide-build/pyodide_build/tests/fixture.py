import json
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
def fake_xbuildenv_releases_compatible(tmp_path):
    """
    Create a fake metadata file with a single release that is compatible with the local environment.
    """
    local = build_env.local_versions()
    fake_releases = {
        "releases": {
            "0.1.0": {
                "version": "0.1.0",
                "url": "https://example.com/0.1.0.tar.gz",
                "sha256": "1234567890abcdef",
                "python_version": f"{local['python']}.0",
                "emscripten_version": "1.39.8",
            },
        },
    }

    metadata_path = Path(tmp_path) / f"metadata-compat.json"
    metadata_path.write_text(json.dumps(fake_releases))

    yield metadata_path


@pytest.fixture(scope="function")
def fake_xbuildenv_releases_incompatible(tmp_path):
    """
    Create a fake metadata file with a single release that is incompatible with the local environment.
    """
    fake_releases = {
        "releases": {
            "0.1.0": {
                "version": "0.1.0",
                "url": "https://example.com/0.1.0.tar.gz",
                "sha256": "1234567890abcdef",
                "python_version": "4.5.6",
                "emscripten_version": "1.39.8",
            },
        },
    }

    metadata_path = Path(tmp_path) / f"metadata-incompat.json"
    metadata_path.write_text(json.dumps(fake_releases))

    yield metadata_path


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
