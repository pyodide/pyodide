import pytest


def test_runwebworker_different_package_name(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    output = selenium.run_webworker(
        """
        import pyparsing
        pyparsing.__version__
        """
    )
    assert isinstance(output, str)


def test_runwebworker_no_imports(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    output = selenium.run_webworker(
        """
        42
        """
    )
    assert output == 42


def test_runwebworker_missing_import(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    msg = "ModuleNotFoundError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import foo
            """
        )


def test_runwebworker_exception(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            42 / 0
            """
        )


def test_runwebworker_exception_after_import(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import pyparsing
            42 / 0
            """
        )


def test_runwebworker_micropip(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    if selenium.browser == "firefox" and script_type == 'module':
        pytest.xfail("firefox doesnot support module type web worker")
    output = selenium.run_webworker(
        """
        import micropip
        await micropip.install('snowballstemmer')
        import snowballstemmer
        stemmer = snowballstemmer.stemmer('english')
        stemmer.stemWords('go goes going gone'.split())[0]
        """
    )
    assert output == "go"
