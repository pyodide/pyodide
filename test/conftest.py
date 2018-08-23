"""
Various common utilities for testing.
"""

import atexit
import multiprocessing
import os
import pathlib
import queue
import sys

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
        if not (BUILD_PATH / 'test.html').exists():
            # selenium does not expose HTTP response codes
            raise ValueError(f"{(BUILD_PATH / 'test.html').resolve()} "
                             f"does not exist!")
        driver.get(f'http://127.0.0.1:{PORT}/test.html')
        wait.until(PyodideInited())
        self.wait = wait
        self.driver = driver

    @property
    def logs(self):
        logs = self.driver.execute_script("return window.logs")
        return '\n'.join(str(x) for x in logs)

    def clean_logs(self):
        self.driver.execute_script("window.logs = []")

    def run(self, code):
        return self.run_js(
            'return pyodide.runPython({!r})'.format(code))

    def run_js(self, code):
        catch = f"""
            Error.stackTraceLimit = Infinity;
            try {{ {code} }}
            catch (error) {{ console.log(error.stack); throw error; }}"""
        return self.driver.execute_script(catch)

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

    browser = 'firefox'

    def get_driver(self):
        from selenium.webdriver import Firefox
        from selenium.webdriver.firefox.options import Options
        from selenium.common.exceptions import JavascriptException

        options = Options()
        options.add_argument('-headless')

        self.JavascriptException = JavascriptException

        return Firefox(
            executable_path='geckodriver', firefox_options=options)


class ChromeWrapper(SeleniumWrapper):

    browser = 'chrome'

    def get_driver(self):
        from selenium.webdriver import Chrome
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import WebDriverException

        options = Options()
        options.add_argument('--headless')

        self.JavascriptException = WebDriverException

        return Chrome(chrome_options=options)


if pytest is not None:
    @pytest.fixture(params=['firefox', 'chrome'])
    def selenium_standalone(request):
        if request.param == 'firefox':
            cls = FirefoxWrapper
        elif request.param == 'chrome':
            cls = ChromeWrapper
        selenium = cls()
        try:
            yield selenium
        finally:
            print(selenium.logs)
            selenium.driver.quit()

    @pytest.fixture(params=['firefox', 'chrome'], scope='module')
    def _selenium_cached(request):
        # Cached selenium instance. This is a copy-paste of
        # selenium_standalone to avoid fixture scope issues
        if request.param == 'firefox':
            cls = FirefoxWrapper
        elif request.param == 'chrome':
            cls = ChromeWrapper
        selenium = cls()
        try:
            yield selenium
        finally:
            selenium.driver.quit()

    @pytest.fixture
    def selenium(_selenium_cached):
        # selenium instance cached at the module level
        try:
            _selenium_cached.clean_logs()
            yield _selenium_cached
        finally:
            print(_selenium_cached.logs)


PORT = 0


def spawn_web_server():
    global PORT

    print("Spawning webserver...")

    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=run_web_server, args=(q,))

    def shutdown_webserver():
        q.put("TERMINATE")
        p.join()
    atexit.register(shutdown_webserver)

    p.start()
    PORT = q.get()


def run_web_server(q):
    import http.server
    import socketserver

    print("Running webserver...")

    os.chdir(BUILD_PATH)
    Handler = http.server.SimpleHTTPRequestHandler
    Handler.extensions_map['.wasm'] = 'application/wasm'

    def dummy_log(*args, **kwargs):
        pass
    Handler.log_message = dummy_log

    with socketserver.TCPServer(("", 0), Handler) as httpd:
        host, port = httpd.server_address
        print("serving at port", port)
        q.put(port)

        def service_actions():
            try:
                if q.get(False) == "TERMINATE":
                    sys.exit(0)
                    httpd.shutdown()
            except queue.Empty:
                pass

        httpd.service_actions = service_actions
        httpd.serve_forever()


@pytest.fixture
def web_server():
    return '127.0.0.1', PORT


if multiprocessing.current_process().name == 'MainProcess':
    spawn_web_server()
