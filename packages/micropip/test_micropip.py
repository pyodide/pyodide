import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pytest_pyodide import run_in_pyodide, spawn_web_server

from conftest import package_is_built

cpver = f"cp{sys.version_info.major}{sys.version_info.minor}"


WHEEL_BASE = None


@pytest.fixture
def wheel_base(monkeypatch):
    with TemporaryDirectory() as tmpdirname:
        global WHEEL_BASE
        WHEEL_BASE = Path(tmpdirname).absolute()
        import site

        monkeypatch.setattr(
            site, "getsitepackages", lambda: [WHEEL_BASE], raising=False
        )
        try:
            yield
        finally:
            WHEEL_BASE = None


@pytest.fixture
@pytest.mark.requires_dynamic_linking
def selenium_standalone_micropip(selenium_standalone):
    """Import micropip before entering test so that global initialization of
    micropip doesn't count towards hiwire refcount.
    """
    
    selenium_standalone.run_js(
        """
        await pyodide.loadPackage("micropip");
        pyodide.runPython("import micropip");
        """
    )
    yield selenium_standalone


SNOWBALL_WHEEL = "snowballstemmer-2.0.0-py2.py3-none-any.whl"


def test_install_simple(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    assert selenium.run_js(
        """
            return await pyodide.runPythonAsync(`
                import os
                import micropip
                from pyodide.ffi import to_js
                # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
                # It is used to test markers support
                await micropip.install('pyodide-micropip-test')
                import snowballstemmer
                stemmer = snowballstemmer.stemmer('english')
                to_js(stemmer.stemWords('go going goes gone'.split()))
            `);
            """
    ) == ["go", "go", "goe", "gone"]


@pytest.mark.parametrize("base_url", ["'{base_url}'", "'.'"])
def test_install_custom_url(selenium_standalone_micropip, base_url):
    selenium = selenium_standalone_micropip

    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + SNOWBALL_WHEEL

        selenium.run_js(
            f"""
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('{url}')
                import snowballstemmer
            `);
            """
        )


@pytest.mark.xfail_browsers(chrome="node only", firefox="node only")
def test_install_file_protocol_node(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    from conftest import DIST_PATH

    pyparsing_wheel_name = list(DIST_PATH.glob("pyparsing*.whl"))[0].name
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install('file:{pyparsing_wheel_name}')
            import pyparsing
        `);
        """
    )


def test_install_different_version(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "https://files.pythonhosted.org/packages/89/06/2c2d3034b4d6bf22f2a4ae546d16925898658a33b4400cfb7e2c1e2871a3/pytz-2020.5-py2.py3-none-any.whl"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


def test_install_different_version2(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "pytz == 2020.5"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_install_mixed_case2(selenium_standalone_micropip, jinja2):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        f"""
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install("{jinja2}")
            import jinja2
        `);
        """
    )


def test_list_load_package_from_url(selenium_standalone_micropip):
    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + SNOWBALL_WHEEL

        selenium = selenium_standalone_micropip
        selenium.run_js(
            f"""
            await pyodide.loadPackage({url!r});
            await pyodide.runPythonAsync(`
                import micropip
                assert "snowballstemmer" in micropip.list()
            `);
            """
        )


def test_list_pyodide_package(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "regex"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


def test_list_loaded_from_js(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.loadPackage("regex");
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


def test_emfs(selenium_standalone_micropip):
    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        url = f"http://{server_hostname}:{server_port}/"

        @run_in_pyodide(packages=["micropip"])
        async def run_test(selenium, url, wheel_name):
            import micropip
            from pyodide.http import pyfetch

            resp = await pyfetch(url + wheel_name)
            await resp._into_file(open(wheel_name, "wb"))
            await micropip.install("emfs:" + wheel_name)
            import snowballstemmer

            stemmer = snowballstemmer.stemmer("english")
            assert stemmer.stemWords("go going goes gone".split()) == [
                "go",
                "go",
                "goe",
                "gone",
            ]

        run_test(selenium_standalone_micropip, url, SNOWBALL_WHEEL)


def test_install_non_normalized_package(selenium_standalone_micropip):
    if not package_is_built("ruamel-yaml"):
        pytest.skip("ruamel.yaml not built")

    selenium = selenium_standalone_micropip

    selenium.run_async(
        """
        import micropip
        await micropip.install("ruamel.yaml")
        import ruamel.yaml
        """
    )
