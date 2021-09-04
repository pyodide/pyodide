from pyodide_build.testing import set_webdriver_script_timeout


class _MockSelenium:
    script_timeout = 2

    def set_script_timeout(self, value):
        self._timeout = value


def test_set_webdriver_script_timeout():
    selenium = _MockSelenium()
    assert not hasattr(selenium, "_timeout")
    with set_webdriver_script_timeout(selenium, script_timeout=10):
        assert selenium._timeout == 10
    assert selenium._timeout == 2
