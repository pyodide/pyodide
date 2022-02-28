import pytest


def test_init(selenium_module_standalone):
    assert (
      "Python initialization complete" in selenium_module_standalone.logs.splitlines()
    )


def test_print(selenium_module_standalone):
    selenium_module_standalone.run("print('This should be logged')")
    assert "This should be logged" in selenium_module_standalone.logs.splitlines()


def test_import_js(selenium_module_standalone):
    if selenium_module_standalone.browser == "node":
        pytest.xfail("No window in node")
    result = selenium_module_standalone.run(
        """
        import js
        js.window.title = 'Foo'
        js.window.title
        """
    )
    assert result == "Foo"
    result = selenium_module_standalone.run(
        """
        dir(js)
        """
    )
    assert len(result) > 100
    assert "document" in result
    assert "window" in result
