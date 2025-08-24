import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
def test_webbrowser_antigravity(selenium):
    # Selenium
    if hasattr(selenium.driver, "window_handles"):
        selenium.run_async("import antigravity")
        assert len(selenium.driver.window_handles) == 2

    # Playwright
    elif hasattr(selenium.driver, "context"):
        with selenium.driver.context.expect_page() as new_page:
            selenium.run_async("import antigravity")
        assert new_page


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
def test_webbrowser_open(selenium):
    # Test basic webbrowser.open functionality
    # Selenium
    if hasattr(selenium.driver, "window_handles"):
        initial_windows = len(selenium.driver.window_handles)
        selenium.run("import webbrowser; webbrowser.open('https://example.com')")
        assert len(selenium.driver.window_handles) == initial_windows + 1

    # Playwright
    elif hasattr(selenium.driver, "context"):
        with selenium.driver.context.expect_page() as new_page:
            selenium.run("import webbrowser; webbrowser.open('https://example.com')")
        assert new_page


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
def test_webbrowser_open_new(selenium):
    # Test webbrowser.open_new functionality
    # Selenium
    if hasattr(selenium.driver, "window_handles"):
        initial_windows = len(selenium.driver.window_handles)
        selenium.run("import webbrowser; webbrowser.open_new('https://example.com')")
        assert len(selenium.driver.window_handles) == initial_windows + 1

    # Playwright
    elif hasattr(selenium.driver, "context"):
        with selenium.driver.context.expect_page() as new_page:
            selenium.run(
                "import webbrowser; webbrowser.open_new('https://example.com')"
            )
        assert new_page


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
def test_webbrowser_open_new_tab(selenium):
    # Test webbrowser.open_new_tab functionality
    # Selenium
    if hasattr(selenium.driver, "window_handles"):
        initial_windows = len(selenium.driver.window_handles)
        selenium.run(
            "import webbrowser; webbrowser.open_new_tab('https://example.com')"
        )
        assert len(selenium.driver.window_handles) == initial_windows + 1

    # Playwright
    elif hasattr(selenium.driver, "context"):
        with selenium.driver.context.expect_page() as new_page:
            selenium.run(
                "import webbrowser; webbrowser.open_new_tab('https://example.com')"
            )
        assert new_page


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
@run_in_pyodide
def test_webbrowser_register_and_get(selenium):
    # Test webbrowser.register and get functionality
    import webbrowser

    # Test registering a custom browser
    class CustomBrowser(webbrowser.BaseBrowser):
        def open(self, url, new=0, autoraise=True):
            return True

    custom_browser = CustomBrowser("custom")
    webbrowser.register("custom", None, custom_browser)

    # Test getting the registered browser
    browser = webbrowser.get("custom")
    assert browser.name == "custom"


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
@run_in_pyodide
def test_webbrowser_error(selenium):
    # Test webbrowser.Error exception
    import webbrowser

    try:
        webbrowser.get("nonexistent_browser")
    except webbrowser.Error as e:
        assert "could not locate runnable browser type" in str(e)


@pytest.mark.xfail_browsers(node="Webbrowser doesn't work in node")
@run_in_pyodide
def test_webbrowser_browser_classes(selenium):
    # Test BaseBrowser and GenericBrowser classes
    import webbrowser

    # Test BaseBrowser
    base_browser = webbrowser.BaseBrowser("test")
    assert base_browser.name == "test" and base_browser.args == ["test"]

    # Test GenericBrowser
    generic_browser = webbrowser.GenericBrowser("generic")
    assert generic_browser.name == "generic"


def test_print(selenium):
    selenium.run("print('This should be logged')")
    assert "This should be logged" in selenium.logs.splitlines()


@pytest.mark.xfail_browsers(node="No window in node")
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


def test_load_package_after_convert_string(selenium):
    """
    See #93.
    """
    selenium.run("import sys; x = sys.version")
    selenium.run_js("let x = pyodide.runPython('x'); console.log(x);")
    selenium.load_package("pytest")
    selenium.run("import pytest")


def test_version_info(selenium):
    from distutils.version import LooseVersion

    version_py_str = selenium.run("import pyodide; pyodide.__version__")
    version_py = LooseVersion(version_py_str)
    assert version_py > LooseVersion("0.0.1")

    version_js_str = selenium.run_js("return pyodide.version;")
    assert version_py_str == version_js_str


@pytest.mark.skip_refcount_check
def test_runpythonasync(selenium_standalone):
    output = selenium_standalone.run_async(
        """
        import micropip
        micropip.__version__
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


@pytest.mark.skip_refcount_check
def test_runpythonasync_exception_after_import(selenium_standalone):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_async(
            """
            import micropip
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
