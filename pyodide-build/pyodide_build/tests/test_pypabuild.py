import pathlib

from pyodide_build import pypabuild
from pyodide_build.common import get_pyversion


class MockIsolatedEnv:
    def __init__(self, temp_path):
        self.path = temp_path
        self.installed = set()

    def install(self, reqs):
        for req in reqs:
            self.installed.add(req)


def test_remove_avoided_requirements():
    assert pypabuild.remove_avoided_requirements(
        {"foo", "bar", "baz"},
        {"foo", "bar", "qux"},
    ) == {"baz"}


def test_install_reqs(tmp_path):
    env = MockIsolatedEnv(tmp_path)

    reqs = {"foo", "bar", "baz"}

    pypabuild.install_reqs(env, reqs)  # type: ignore[arg-type]
    for req in reqs:
        assert req in env.installed

    pypabuild.install_reqs(env, set(pypabuild.AVOIDED_REQUIREMENTS))  # type: ignore[arg-type]
    for req in pypabuild.AVOIDED_REQUIREMENTS:
        assert req not in env.installed


def test_symlink_unisolated_packages(tmp_path):
    env = MockIsolatedEnv(tmp_path)
    pypabuild.symlink_unisolated_packages(env)  # type: ignore[arg-type]
    pyversion = get_pyversion()

    site_packages_path = pathlib.Path(f"{env.path}/lib/{pyversion}/site-packages")
    files = [path.name for path in site_packages_path.glob("*.py")]

    assert "_sysconfigdata__emscripten_wasm32-emscripten.py" in files
