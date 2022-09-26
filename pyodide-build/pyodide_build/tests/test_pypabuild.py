from pyodide_build import pypabuild


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
