import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pytest_pyodide import run_in_pyodide

cpver = f"cp{sys.version_info.major}{sys.version_info.minor}"


WHEEL_BASE = None
SNOWBALL_WHEEL = (
    Path(__file__).parent / "test" / "snowballstemmer-2.0.0-py2.py3-none-any.whl"
)


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


def test_install_custom_url(selenium_standalone_micropip, httpserver):
    selenium = selenium_standalone_micropip

    httpserver.expect_oneshot_request(f"/{SNOWBALL_WHEEL.name}").respond_with_data(
        SNOWBALL_WHEEL.read_bytes(),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    url = httpserver.url_for(SNOWBALL_WHEEL.name)

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

    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install('file:{SNOWBALL_WHEEL.as_posix()}')
            import snowballstemmer
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


def test_list_load_package_from_url(selenium_standalone_micropip, httpserver):
    httpserver.expect_oneshot_request(f"/{SNOWBALL_WHEEL.name}").respond_with_data(
        SNOWBALL_WHEEL.read_bytes(),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    url = httpserver.url_for(SNOWBALL_WHEEL.name)

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


def test_emfs(selenium_standalone_micropip, httpserver):
    httpserver.expect_oneshot_request(f"/{SNOWBALL_WHEEL.name}").respond_with_data(
        SNOWBALL_WHEEL.read_bytes(),
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    url = httpserver.url_for(f"/{SNOWBALL_WHEEL.name}")

    @run_in_pyodide(packages=["micropip"])
    async def run_test(selenium, url, wheel_name):
        import micropip
        from pyodide.http import pyfetch

        resp = await pyfetch(url)
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

    run_test(selenium_standalone_micropip, url, SNOWBALL_WHEEL.name)
