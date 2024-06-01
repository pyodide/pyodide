import json
import os
from pathlib import Path

import pytest

from pyodide_build import build_env
from pyodide_build.common import xbuildenv_dirname
from pyodide_build.xbuildenv import CrossBuildEnvManager


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

    def _reset():
        build_env.get_pyodide_root.cache_clear()
        build_env.get_build_environment_vars.cache_clear()
        build_env.get_unisolated_packages.cache_clear()

    _reset()

    yield _reset


@pytest.fixture(scope="function")
def dummy_xbuildenv_url(httpserver):
    """
    Returns the URL of a dummy xbuildenv archive.
    This archive contains a minimal files that are required to install a xbuildenv.
    """
    test_xbuildenv_archive_path = (
        Path(__file__).parent / "_test_xbuildenv" / "xbuildenv-test.tar.gz"
    )
    test_xbuildenv_archive = test_xbuildenv_archive_path.read_bytes()

    httpserver.expect_request("/xbuildenv-test.tar.gz").respond_with_data(
        test_xbuildenv_archive
    )
    yield httpserver.url_for("/xbuildenv-test.tar.gz")


@pytest.fixture(scope="function")
def dummy_xbuildenv(dummy_xbuildenv_url, tmp_path, reset_env_vars, reset_cache):
    """
    Downloads the dummy xbuildenv archive and installs it in the temporary directory.

    This fixture can be used to run any functions that require a xbuildenv to be installed before running.
    """
    assert "PYODIDE_ROOT" not in os.environ

    manager = CrossBuildEnvManager(tmp_path / xbuildenv_dirname())
    manager.install(
        version=None, url=dummy_xbuildenv_url, skip_install_cross_build_packages=True
    )

    cur_dir = os.getcwd()

    os.chdir(tmp_path)

    try:
        yield tmp_path
    finally:
        os.chdir(cur_dir)


class MockEmscripten:
    def __init__(self, log_file: Path):
        self.log_file = log_file

    def capture_output(self) -> list[str]:
        return self.log_file.read_text().splitlines()


MOCK_EMSCRIPTEN_TEMPLATE = (
    Path(__file__).parent / "utils" / "mock_emscripten.sh.tmpl"
).read_text()


@pytest.fixture(scope="function")
def mock_emscripten(tmp_path, dummy_xbuildenv, reset_env_vars, reset_cache):
    """
    This fixture makes a fake emscripten compilers in the PATH.
    TODO: make this fixture more smart and flexible.
    """
    emscripten_version = build_env.get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")

    mock_dir = Path(tmp_path).resolve()
    mock_dir.mkdir(exist_ok=True, parents=True)

    emcc_log_file = mock_dir / "emcc.log"
    emcc_binary = mock_dir / "emcc"
    emcc_binary.write_text(
        MOCK_EMSCRIPTEN_TEMPLATE.format(
            output_file=emcc_log_file, version=emscripten_version
        )
    )
    emcc_binary.chmod(0o755)

    llvm_readobj_log_file = mock_dir / "llvm-readobj.log"
    llvm_readobj_binary = mock_dir / "llvm-readobj"
    llvm_readobj_binary.write_text(
        MOCK_EMSCRIPTEN_TEMPLATE.format(
            output_file=llvm_readobj_log_file, version=emscripten_version
        )
    )
    llvm_readobj_binary.chmod(0o755)

    original_path = os.environ["PATH"]

    os.environ["PATH"] = f"{mock_dir}:{original_path}"
    reset_cache()

    yield {
        "emcc": MockEmscripten(emcc_log_file),
        "llvm-readobj": MockEmscripten(llvm_readobj_log_file),
    }

    os.environ["PATH"] = original_path


@pytest.fixture(scope="function")
def fake_xbuildenv_releases_compatible(tmp_path, dummy_xbuildenv_url):
    """
    Create a fake metadata file with a single release that is compatible with the local environment.
    """
    local = build_env.local_versions()
    fake_releases = {
        "releases": {
            "0.1.0": {
                "version": "0.1.0",
                "url": dummy_xbuildenv_url,
                "sha256": "1234567890abcdef",
                "python_version": f"{local['python']}.0",
                "emscripten_version": "1.39.8",
            },
            "0.2.0": {
                "version": "0.2.0",
                "url": dummy_xbuildenv_url,
                "sha256": "1234567890abcdef",
                "python_version": f"{local['python']}.0",
                "emscripten_version": "2.39.8",
            },
        },
    }

    metadata_path = Path(tmp_path) / "metadata-compat.json"
    metadata_path.write_text(json.dumps(fake_releases))

    yield metadata_path


@pytest.fixture(scope="function")
def fake_xbuildenv_releases_incompatible(tmp_path, dummy_xbuildenv_url):
    """
    Create a fake metadata file with a single release that is incompatible with the local environment.
    """
    fake_releases = {
        "releases": {
            "0.1.0": {
                "version": "0.1.0",
                "url": dummy_xbuildenv_url,
                "sha256": "1234567890abcdef",
                "python_version": "4.5.6",
                "emscripten_version": "1.39.8",
            },
        },
    }

    metadata_path = Path(tmp_path) / "metadata-incompat.json"
    metadata_path.write_text(json.dumps(fake_releases))

    yield metadata_path
