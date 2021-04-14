import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent / "micropip"))


@pytest.fixture
def selenium_standalone_micropip(selenium_standalone):
    """Import micropip before entering test so that global initialization of
    micropip doesn't count towards hiwire refcount.
    """
    selenium_standalone.run_js(
        """
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync("import micropip");
        """
    )
    yield selenium_standalone


def test_install_simple(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    assert (
        selenium.run_js(
            """
            let result = await pyodide.runPythonAsync(`
                import os
                import micropip
                # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
                # It is used to test markers support
                await micropip.install('pyodide-micropip-test')
                import snowballstemmer
                stemmer = snowballstemmer.stemmer('english')
                stemmer.stemWords('go going goes gone'.split())
            `);
            return result.toJs();
            """
        )
        == ["go", "go", "goe", "gone"]
    )


def test_parse_wheel_url():
    pytest.importorskip("distlib")
    import micropip

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


def test_install_custom_url(selenium_standalone_micropip, web_server_tst_data):
    selenium = selenium_standalone_micropip
    server_hostname, server_port, server_log = web_server_tst_data
    base_url = f"http://{server_hostname}:{server_port}/"
    url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install('{url}')
            import snowballstemmer
        `);
        """
    )


def test_add_requirement_relative_url():
    pytest.importorskip("distlib")
    import micropip

    transaction = {"wheels": []}
    coroutine = micropip.PACKAGE_MANAGER.add_requirement(
        "./snowballstemmer-2.0.0-py2.py3-none-any.whl", {}, transaction
    )
    # The following is a way to synchronously run a coroutine that does only
    # synchronous operations (and assert that it indeed only did synch
    # operations)
    try:
        coroutine.send(None)
    except StopIteration as _result:
        pass
    else:
        raise Exception("Coroutine didn't finish in one pass")

    [name, req, version] = transaction["wheels"][0]
    assert name == "snowballstemmer"
    assert version == "2.0.0"
    assert req["filename"] == "snowballstemmer-2.0.0-py2.py3-none-any.whl"
    assert req["packagetype"] == "bdist_wheel"
    assert req["python_version"] == "py2.py3"
    assert req["abi_tag"] == "none"
    assert req["platform"] == "any"
    assert req["url"] == "./snowballstemmer-2.0.0-py2.py3-none-any.whl"


def test_install_custom_relative_url(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    root = Path(__file__).resolve().parents[2]
    src = root / "src" / "tests" / "data"
    target = root / "build" / "test_data"
    target.symlink_to(src, True)
    url = "./test_data/snowballstemmer-2.0.0-py2.py3-none-any.whl"
    try:
        selenium.run_js(
            f"""
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('{url}')
                import snowballstemmer
            `)
            """
        )
    finally:
        target.unlink()


def test_last_version_from_pypi():
    pytest.importorskip("distlib")
    import micropip

    class Namespace:
        def __init__(self, **entries):
            self.__dict__.update(entries)

    # requirement as returned by distlib.util.parse_requirement
    requirement = Namespace(
        constraints=None,
        extras=None,
        marker=None,
        name="dummy_module",
        requirement="dummy_module",
        url=None,
    )

    # available versions
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

    assert ver == "0.15.5"


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
