import pytest


def test_runwebworker_different_package_name(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        import pyparsing
        pyparsing.__version__
        """
    )
    assert isinstance(output, str)


def test_runwebworker_no_imports(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        42
        """
    )
    assert output == 42


def test_runwebworker_missing_import(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
    msg = "ModuleNotFoundError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import foo
            """
        )


def test_runwebworker_exception(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            42 / 0
            """
        )


def test_runwebworker_exception_after_import(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import pyparsing
            42 / 0
            """
        )


def test_runwebworker_micropip(selenium_webworker_standalone):
    selenium = selenium_webworker_standalone
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
