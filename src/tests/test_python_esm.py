import pytest


def test_init(selenium_esm):
    assert "Python initialization complete" in selenium_esm.logs.splitlines()


def test_print(selenium_esm):
    selenium_esm.run("print('This should be logged')")
    assert "This should be logged" in selenium_esm.logs.splitlines()


def test_import_js(selenium_esm):
    if selenium_esm.browser == "node":
        pytest.xfail("No window in node")
    result = selenium_esm.run(
        """
        import js
        js.window.title = 'Foo'
        js.window.title
        """
    )
    assert result == "Foo"
    result = selenium_esm.run(
        """
        dir(js)
        """
    )
    assert len(result) > 100
    assert "document" in result
    assert "window" in result
