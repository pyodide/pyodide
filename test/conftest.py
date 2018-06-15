"""
Various common utilities for testing.
"""

import pathlib
import time

try:
    import pytest
except ImportError:
    pytest = None


TEST_PATH = pathlib.Path(__file__).parents[0].resolve()
BUILD_PATH = TEST_PATH / '..' / 'build'


class PyodideInited:
    def __call__(self, driver):
        inited = driver.execute_script(
            "return window.pyodide && window.pyodide.runPython")
        return inited is not None


class PackageLoaded:
    def __call__(self, driver):
        inited = driver.execute_script(
            "return window.done")
        return bool(inited)


class SeleniumWrapper:
    def __init__(self):
        from selenium.webdriver import Firefox
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.support.wait import WebDriverWait

        options = Options()
        options.add_argument('-headless')
        driver = Firefox(
            executable_path='geckodriver', firefox_options=options)
        wait = WebDriverWait(driver, timeout=20)
        driver.get((BUILD_PATH / "test.html").as_uri())
        wait.until(PyodideInited())
        self.wait = wait
        self.driver = driver

    @property
    def logs(self):
        return self.driver.execute_script("return window.logs")

    def run(self, code):
        return self.run_js(
            'return pyodide.runPython({!r})'.format(code))

    def run_js(self, code):
        return self.driver.execute_script(code)

    def load_package(self, packages):
        self.run_js(
            'window.done = false\n'
            'pyodide.loadPackage({!r}).then(window.done = true)'.format(
                packages))
        time.sleep(2)
        self.wait.until(PackageLoaded())

    @property
    def urls(self):
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            yield self.driver.current_url


if pytest is not None:
    @pytest.fixture
    def selenium():
        selenium = SeleniumWrapper()
        try:
            yield selenium
        finally:
            print('\n'.join(str(x) for x in selenium.logs))
            selenium.driver.quit()
