import pytest


def test_runwebworker_different_package_name(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        import pyparsing
        pyparsing.__version__
        """
    )
    assert isinstance(output, str)


def test_runwebworker_no_imports(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        42
        """
    )
    assert output == 42


def test_runwebworker_missing_import(selenium_standalone):
    msg = "ModuleNotFoundError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_webworker(
            """
            import foo
            """
        )


def test_runwebworker_exception(selenium_standalone):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_webworker(
            """
            42 / 0
            """
        )


def test_runwebworker_exception_after_import(selenium_standalone):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium_standalone.JavascriptException, match=msg):
        selenium_standalone.run_webworker(
            """
            import pyparsing
            42 / 0
            """
        )


def test_runwebworker_micropip(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        def stem(*args):
            import snowballstemmer
            stemmer = snowballstemmer.stemmer('english')
            return stemmer.stemWords('go goes going gone'.split())[0]
        import micropip
        micropip.install('snowballstemmer').then(stem)
        """
    )
    assert output == "go"
