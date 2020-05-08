def test_runwebworker(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        import numpy as np
        x = np.zeros(5)
        str(x)
        """
    )
    assert output == '[0. 0. 0. 0. 0.]'


def test_runwebworker_different_package_name(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        import dateutil
        dateutil.__version__
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
    try:
        selenium_standalone.run_webworker(
            """
            import foo
            """
        )
    except selenium_standalone.JavascriptException as e:
        assert "ModuleNotFoundError" in str(e)
    else:
        assert False


def test_runwebworker_exception(selenium_standalone):
    try:
        selenium_standalone.run_webworker(
            """
            42 / 0
            """
        )
    except selenium_standalone.JavascriptException as e:
        assert "ZeroDivisionError" in str(e)
    else:
        assert False


def test_runwebworker_exception_after_import(selenium_standalone):
    try:
        selenium_standalone.run_webworker(
            """
            import numpy as np
            x = np.empty(5)
            42 / 0
            """
        )
    except selenium_standalone.JavascriptException as e:
        assert "ZeroDivisionError" in str(e)
    else:
        assert False


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
    assert output == 'go'
