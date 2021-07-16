import pytest


def test_init(selenium_standalone):
    selenium = selenium_standalone
    assert "Python initialization complete" in selenium.logs.splitlines()
    selenium.run("import antigravity")

def test_print(selenium):
    selenium.run("print('This should be logged')")
    assert "This should be logged" in selenium.logs.splitlines()

def test_import_js(selenium):
    result = selenium.run(
        """
        import js
        js.window.title = 'Foo'
        js.window.title
        """
    )
    assert result == "Foo"
    result = selenium.run(
        """
        dir(js)
        """
    )
    assert len(result) > 100
    assert "document" in result
    assert "window" in result


def test_globals_get_multiple(selenium):
    """See #1151"""
    selenium.run_js(
        """
        pyodide.runPython("v = 0.123");
        pyodide.globals.get('v')
        pyodide.globals.get('v')
        """
    )


def test_open_url(selenium, httpserver):
    httpserver.expect_request("/data").respond_with_data(
        b"HELLO", content_type="text/text", headers={"Access-Control-Allow-Origin": "*"}
    )
    request_url = httpserver.url_for("/data")

    assert (
        selenium.run(
            f"""
        import pyodide
        pyodide.open_url('{request_url}').read()
        """
        )
        == "HELLO"
    )


def test_load_package_after_convert_string(selenium):
    """
    See #93.
    """
    selenium.run("import sys; x = sys.version")
    selenium.run_js("let x = pyodide.runPython('x'); console.log(x);")
    selenium.load_package("pytz")
    selenium.run("import pytz")


def test_version_info(selenium):
    from distutils.version import LooseVersion

    version_py_str = selenium.run("import pyodide; pyodide.__version__")
    version_py = LooseVersion(version_py_str)
    assert version_py > LooseVersion("0.0.1")

    version_js_str = selenium.run_js("return pyodide.version;")
    assert version_py_str == version_js_str


def test_runpythonasync(selenium_standalone):
    output = selenium_standalone.run_async(
        """
        import pyparsing
        pyparsing.__version__
        """
    )
    assert isinstance(output, str)


def test_runpythonasync_no_imports(selenium_standalone):
    output = selenium_standalone.run_async(
        """
        42
        """
    )
    assert output == 42


def test_runpythonasync_missing_import(selenium_standalone):
    msg = "ModuleNotFoundError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_async(
            """
            import foo
            """
        )


def test_runpythonasync_exception(selenium_standalone):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_async(
            """
            42 / 0
            """
        )


def test_runpythonasync_exception_after_import(selenium_standalone):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_async(
            """
            import pyparsing
            42 / 0
            """
        )


def test_py(selenium_standalone):
    selenium_standalone.run_js(
        """
        pyodide.runPython(`
            def func():
                return 42
        `);
        let func = pyodide.globals.get('func');
        assert(() => func() === 42);
        func.destroy();
        """
    )


def test_eval_nothing(selenium):
    assert selenium.run("# comment") is None
    assert selenium.run("") is None


def test_unknown_attribute(selenium):
    selenium.run_async(
        """
        from unittest import TestCase
        raises = TestCase().assertRaisesRegex
        import js
        with raises(AttributeError, "asdf"):
            js.asdf
        """
    )
