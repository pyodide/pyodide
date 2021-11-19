import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent / "src"))


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
    assert (
        selenium.run_js(
            """
            return await pyodide.runPythonAsync(`
                import os
                import micropip
                from pyodide import to_js
                # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
                # It is used to test markers support
                await micropip.install('pyodide-micropip-test')
                import snowballstemmer
                stemmer = snowballstemmer.stemmer('english')
                to_js(stemmer.stemWords('go going goes gone'.split()))
            `);
            """
        )
        == ["go", "go", "goe", "gone"]
    )


def test_parse_wheel_url():
    pytest.importorskip("packaging")
    from micropip import micropip

    url = "https://a/snowballstemmer-2.0.0-py2.py3-none-any.whl"
    name, wheel, version = micropip._parse_wheel_url(url)
    assert name == "snowballstemmer"
    assert version == "2.0.0"
    assert wheel == {
        "digests": None,
        "filename": "snowballstemmer-2.0.0-py2.py3-none-any.whl",
        "packagetype": "bdist_wheel",
        "python_version": "py2.py3",
        "abi_tag": "none",
        "platform": "any",
        "url": url,
    }

    msg = "not a valid wheel file name"
    with pytest.raises(ValueError, match=msg):
        url = "https://a/snowballstemmer-2.0.0-py2.whl"
        name, params, version = micropip._parse_wheel_url(url)

    url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
    name, wheel, version = micropip._parse_wheel_url(url)
    assert name == "scikit_learn"
    assert wheel["platform"] == "macosx_10_9_intel"


@pytest.mark.parametrize("base_url", ["'{base_url}'", "'.'"])
def test_install_custom_url(selenium_standalone_micropip, base_url):
    selenium = selenium_standalone_micropip
    base_url = base_url.format(base_url=selenium.base_url)

    root = Path(__file__).resolve().parents[2]
    src = root / "src" / "tests" / "data"
    target = root / "build" / "test_data"
    target.symlink_to(src, True)
    path = "/test_data/snowballstemmer-2.0.0-py2.py3-none-any.whl"
    try:
        selenium.run_js(
            f"""
            let url = {base_url} + '{path}';
            let resp = await fetch(url);
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('${{url}}')
                import snowballstemmer
            `);
            """
        )
    finally:
        target.unlink()


def test_add_requirement(web_server_tst_data):
    pytest.importorskip("packaging")
    from micropip import micropip

    server_hostname, server_port, server_log = web_server_tst_data
    base_url = f"http://{server_hostname}:{server_port}/"
    url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"

    transaction = {"wheels": [], "locked": {}}
    asyncio.get_event_loop().run_until_complete(
        micropip.PACKAGE_MANAGER.add_requirement(url, {}, transaction)
    )

    [name, req, version] = transaction["wheels"][0]
    assert name == "snowballstemmer"
    assert version == "2.0.0"
    assert req["filename"] == "snowballstemmer-2.0.0-py2.py3-none-any.whl"
    assert req["packagetype"] == "bdist_wheel"
    assert req["python_version"] == "py2.py3"
    assert req["abi_tag"] == "none"
    assert req["platform"] == "any"
    assert req["url"] == url


def test_add_requirement_marker():
    pytest.importorskip("packaging")
    from micropip import micropip

    transaction = asyncio.get_event_loop().run_until_complete(
        micropip.PACKAGE_MANAGER.gather_requirements(
            [
                "werkzeug",
                'contextvars ; python_version < "3.7"',
                'aiocontextvars ; python_version < "3.7"',
                "numpy ; extra == 'full'",
                "zarr ; extra == 'full'",
                "numpy ; extra == 'jupyter'",
                "ipykernel ; extra == 'jupyter'",
                "numpy ; extra == 'socketio'",
                "python-socketio[client] ; extra == 'socketio'",
            ]
        )
    )
    assert len(transaction["wheels"]) == 1


def test_last_version_from_pypi():
    pytest.importorskip("packaging")
    from micropip import micropip
    from packaging.requirements import Requirement

    requirement = Requirement("dummy_module")
    versions = ["0.0.1", "0.15.5", "0.9.1"]

    # building metadata as returned from
    # https://pypi.org/pypi/{pkgname}/json
    metadata = {
        "releases": {
            v: [{"filename": f"dummy_module-{v}-py3-none-any.whl"}] for v in versions
        }
    }

    # get version number from find_wheel
    wheel, ver = micropip.PACKAGE_MANAGER.find_wheel(metadata, requirement)

    assert str(ver) == "0.15.5"


def test_install_non_pure_python_wheel():
    pytest.importorskip("packaging")
    from micropip import micropip

    msg = "not a pure Python 3 wheel"
    with pytest.raises(ValueError, match=msg):
        url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        transaction = {"wheels": [], "locked": {}}
        asyncio.get_event_loop().run_until_complete(
            micropip.PACKAGE_MANAGER.add_requirement(url, {}, transaction)
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


def test_report_all_failed_dependencies(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import micropip

    async def _mock_get_pypi_json(pkgname, **kwargs):
        return {
            "releases": {
                "1.0.0": [
                    {
                        "filename": f"{pkgname}-1.0.0.tar.gz",
                    }
                ]
            }
        }

    monkeypatch.setattr(micropip, "_get_pypi_json", _mock_get_pypi_json)

    # dummy package which requires both tensorflow and torch
    pkg = "https://files.pythonhosted.org/packages/e7/a2/dcc325ea62aea0973dcd4474f3fc0946ac4074c4f9789c9757317b4f786b/nonpure_dummy-0.0.1-py3-none-any.whl"

    # report order is non-deterministic
    msg = "[torch|tensorflow].*[torch|tensorflow]"
    with pytest.raises(ValueError, match=msg):
        asyncio.get_event_loop().run_until_complete(micropip.install(pkg))
