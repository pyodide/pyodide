import asyncio
import io
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pyodide_test_runner import run_in_pyodide, spawn_web_server

sys.path.append(str(Path(__file__).resolve().parent / "src"))


def mock_get_pypi_json(pkg_map):
    """Returns mock function of `_get_pypi_json` which returns dummy JSON data of PyPI API.

    Parameters
    ----------
    pkg_map : ``None | Dict[str, str]``

        Dictionary that maps package name to dummy release file.
        Packages that are not in this dictionary will return
        `{pkgname}-1.0.0.tar.gz` as a release file.

    Returns
    -------
    ``Function``
        A mock function of ``_get_pypi_json`` which returns dummy JSON data of PyPI API.
    """

    class Wildcard:
        def __eq__(self, other):
            return True

    async def _mock_get_pypi_json(pkgname, **kwargs):
        if pkgname in pkg_map:
            pkg_file = pkg_map[pkgname]
        else:
            pkg_file = f"{pkgname}-1.0.0.tar.gz"

        return {
            "releases": {
                "1.0.0": [
                    {
                        "filename": pkg_file,
                        "url": "",
                        "digests": {
                            "sha256": Wildcard(),
                        },
                    }
                ]
            }
        }

    return _mock_get_pypi_json


def mock_fetch_bytes(pkg_name, metadata, version="1.0.0"):
    """Returns mock function of `fetch_bytes` which returns dummy wheel bytes.

    Parameters
    ----------
    pkg_name : ``str``
        Name of the Python package

    metadata : ``str``
        Metadata of the dummy wheel file

    version : ``str``
        Version of the dummy wheel file

    Returns
    -------
    ``Function``
        A mock function of ``fetch_bytes`` which return dummy wheel bytes
    """

    async def _mock_fetch_bytes(url, **kwargs):
        mock_metadata = metadata
        mock_wheel = "Wheel-Version: 1.0"

        with io.BytesIO() as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    f"{pkg_name}-{version}.dist-info/METADATA", mock_metadata
                )
                archive.writestr(f"{pkg_name}-{version}.dist-info/WHEEL", mock_wheel)

            tmp.seek(0)

            return tmp.read()

    return _mock_fetch_bytes


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
    from micropip import _micropip

    url = "https://a/snowballstemmer-2.0.0-py2.py3-none-any.whl"
    name, wheel, version = _micropip._parse_wheel_url(url)
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
        name, params, version = _micropip._parse_wheel_url(url)

    url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
    name, wheel, version = _micropip._parse_wheel_url(url)
    assert name == "scikit_learn"
    assert wheel["platform"] == "macosx_10_9_intel"


@pytest.mark.parametrize("base_url", ["'{base_url}'", "'.'"])
def test_install_custom_url(selenium_standalone_micropip, base_url):
    selenium = selenium_standalone_micropip

    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"

        selenium.run_js(
            f"""
            let url = '{url}';
            let resp = await fetch(url);
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('${{url}}')
                import snowballstemmer
            `);
            """
        )


def test_add_requirement():
    pytest.importorskip("packaging")
    from micropip import _micropip

    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"

    transaction: dict[str, Any] = {
        "wheels": [],
        "locked": {},
        "keep_going": True,
        "deps": True,
    }
    asyncio.get_event_loop().run_until_complete(
        _micropip.PACKAGE_MANAGER.add_requirement(url, {}, transaction)
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
    from micropip import _micropip

    transaction = asyncio.get_event_loop().run_until_complete(
        _micropip.PACKAGE_MANAGER.gather_requirements(
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
    from packaging.requirements import Requirement

    from micropip import _micropip

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
    wheel, ver = _micropip.PACKAGE_MANAGER.find_wheel(metadata, requirement)

    assert str(ver) == "0.15.5"


def test_install_non_pure_python_wheel():
    pytest.importorskip("packaging")
    from micropip import _micropip

    msg = "not a pure Python 3 wheel"
    with pytest.raises(ValueError, match=msg):
        url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        transaction = {"wheels": list[Any](), "locked": dict[str, Any]()}
        asyncio.get_event_loop().run_until_complete(
            _micropip.PACKAGE_MANAGER.add_requirement(url, {}, transaction)
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


def test_install_keep_going(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    dummy_pkg_name = "dummy"
    _mock_get_pypi_json = mock_get_pypi_json(
        {dummy_pkg_name: f"{dummy_pkg_name}-1.0.0-py3-none-any.whl"}
    )
    _mock_fetch_bytes = mock_fetch_bytes(
        dummy_pkg_name, "Requires-Dist: dep1\nRequires-Dist: dep2\n\nUNKNOWN"
    )

    monkeypatch.setattr(_micropip, "_get_pypi_json", _mock_get_pypi_json)
    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    # report order is non-deterministic
    msg = "(dep1|dep2).*(dep2|dep1)"
    with pytest.raises(ValueError, match=msg):
        asyncio.get_event_loop().run_until_complete(
            _micropip.install(dummy_pkg_name, keep_going=True)
        )


def test_install_no_deps(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    dummy_pkg_name = "dummy"
    dep_pkg_name = "dependency_dummy"
    _mock_get_pypi_json = mock_get_pypi_json(
        {
            dummy_pkg_name: f"{dummy_pkg_name}-1.0.0-py3-none-any.whl",
            dep_pkg_name: f"{dep_pkg_name}-1.0.0-py3-none-any.whl",
        }
    )
    _mock_fetch_bytes = mock_fetch_bytes(
        dummy_pkg_name, f"Requires-Dist: {dep_pkg_name}\n\nUNKNOWN"
    )

    monkeypatch.setattr(_micropip, "_get_pypi_json", _mock_get_pypi_json)
    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    asyncio.get_event_loop().run_until_complete(
        _micropip.install(dummy_pkg_name, deps=False)
    )

    assert dummy_pkg_name in _micropip._list()
    assert dep_pkg_name not in _micropip._list()


def test_fetch_wheel_fail(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    def _mock_fetch_bytes(*args, **kwargs):
        raise Exception("Failed to fetch")

    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    msg = "Access-Control-Allow-Origin"
    with pytest.raises(ValueError, match=msg):
        asyncio.get_event_loop().run_until_complete(
            _micropip.install("htps://x.com/xxx-1.0.0-py3-none-any.whl")
        )


def test_list_pypi_package(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    dummy_pkg_name = "dummy"
    _mock_get_pypi_json = mock_get_pypi_json(
        {dummy_pkg_name: f"{dummy_pkg_name}-1.0.0-py3-none-any.whl"}
    )
    _mock_fetch_bytes = mock_fetch_bytes(dummy_pkg_name, "UNKNOWN")

    monkeypatch.setattr(_micropip, "_get_pypi_json", _mock_get_pypi_json)
    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    asyncio.get_event_loop().run_until_complete(_micropip.install(dummy_pkg_name))

    pkg_list = _micropip._list()
    assert "dummy" in pkg_list and pkg_list["dummy"].source.lower() == "pypi"


def test_list_wheel_package(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    dummy_pkg_name = "dummy"
    dummy_url = f"https://dummy.com/{dummy_pkg_name}-1.0.0-py3-none-any.whl"
    _mock_fetch_bytes = mock_fetch_bytes(dummy_pkg_name, "UNKNOWN")

    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    asyncio.get_event_loop().run_until_complete(_micropip.install(dummy_url))

    pkg_list = _micropip._list()
    assert "dummy" in pkg_list and pkg_list["dummy"].source.lower() == dummy_url


def test_list_wheel_name_mismatch(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    dummy_pkg_name = "dummy-Dummy"
    normalized_pkg_name = dummy_pkg_name.replace("-", "_").lower()
    dummy_url = f"https://dummy.com/{normalized_pkg_name}-1.0.0-py3-none-any.whl"
    _mock_fetch_bytes = mock_fetch_bytes(dummy_pkg_name, f"Name: {dummy_pkg_name}")

    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    asyncio.get_event_loop().run_until_complete(_micropip.install(dummy_url))

    pkg_list = _micropip._list()
    assert (
        dummy_pkg_name in pkg_list
        and pkg_list[dummy_pkg_name].source.lower() == dummy_url
        and pkg_list[dummy_pkg_name].name == dummy_pkg_name
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
            assert "regex" in pkgs and pkgs["regex"].source.lower() == "pyodide"
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
            assert "regex" in pkgs and pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_install_with_credentials():
    import json
    from unittest.mock import MagicMock, patch

    import micropip

    fetch_response_mock = MagicMock()

    async def myfunc():
        return json.dumps(dict())

    fetch_response_mock.string.side_effect = myfunc

    @patch("micropip._micropip.pyfetch", return_value=fetch_response_mock)
    async def call_micropip_install(pyfetch_mock):
        try:
            await micropip.install("pyodide-micropip-test", credentials="include")
        except BaseException:
            # The above will raise an exception as the mock data is garbage
            # but it is sufficient for this test
            pass
        pyfetch_mock.assert_called_with(
            "https://pypi.org/pypi/pyodide-micropip-test/json", credentials="include"
        )

    await call_micropip_install()
