from pyodide_build.testing import set_webdriver_script_timeout


class _MockDriver:
    def set_script_timeout(self, value):
        self._timeout = value


class _MockSelenium:
    script_timeout = 2
    driver = _MockDriver()


def test_set_webdriver_script_timeout():
    selenium = _MockSelenium()
    assert not hasattr(selenium.driver, "_timeout")
    with set_webdriver_script_timeout(selenium, script_timeout=10):
        assert selenium.driver._timeout == 10
    assert selenium.driver._timeout == 2
