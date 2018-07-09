"""
Various common utilities for testing.
"""

import atexit
import multiprocessing
import os
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
        from selenium.webdriver.support.wait import WebDriverWait

        driver = self.get_driver()
        wait = WebDriverWait(driver, timeout=20)
        driver.get('http://127.0.0.1:8000/test.html')
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
            'window.done = false\n' +
            'pyodide.loadPackage({!r})'.format(packages) +
            '.then(function() { window.done = true; })')
        self.wait.until(PackageLoaded())

    @property
    def urls(self):
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            yield self.driver.current_url


class FirefoxWrapper(SeleniumWrapper):
    def get_driver(self):
        from selenium.webdriver import Firefox
        from selenium.webdriver.firefox.options import Options

        options = Options()
        options.add_argument('-headless')
        return Firefox(
            executable_path='geckodriver', firefox_options=options)


class ChromeWrapper(SeleniumWrapper):
    def get_driver(self):
        from selenium.webdriver import Chrome
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument('--headless')
        return Chrome(chrome_options=options)


if pytest is not None:
    @pytest.fixture(params=['firefox', 'chrome'])
    def selenium(request):
        if request.param == 'firefox':
            cls = FirefoxWrapper
        elif request.param == 'chrome':
            cls = ChromeWrapper
        selenium = cls()
        try:
            yield selenium
        finally:
            print('\n'.join(str(x) for x in selenium.logs))
            selenium.driver.quit()


def spawn_web_server():
    print("Spawning webserver...")

    p = multiprocessing.Process(target=run_web_server)

    def shutdown_webserver():
        p.terminate()
    atexit.register(shutdown_webserver)

    p.start()
    time.sleep(2)


def run_web_server():
    import http.server
    import socketserver

    print("Running webserver...")

    os.chdir(BUILD_PATH)
    PORT = 8000
    Handler = http.server.SimpleHTTPRequestHandler
    Handler.extensions_map['.wasm'] = 'application/wasm'

    def dummy_log(*args, **kwargs):
        pass
    Handler.log_message = dummy_log

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        httpd.serve_forever()


if multiprocessing.current_process().name == 'MainProcess':
    spawn_web_server()
