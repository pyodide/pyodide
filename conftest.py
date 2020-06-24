"""
Various common utilities for testing.
"""

import contextlib
import multiprocessing
import textwrap
import tempfile
import time
import os
import pathlib
import queue
import sys
import shutil

ROOT_PATH = pathlib.Path(__file__).parents[0].resolve()
TEST_PATH = ROOT_PATH / "test"
BUILD_PATH = ROOT_PATH / 'build'

sys.path.append(str(ROOT_PATH))

from pyodide_build._fixes import _selenium_is_connectable  # noqa: E402
import selenium.webdriver.common.utils  # noqa: E402

# XXX: Temporary fix for ConnectionError in selenium

selenium.webdriver.common.utils.is_connectable = _selenium_is_connectable

collect_ignore_glob = ['packages/*/*/*']

try:
    import pytest

    def pytest_addoption(parser):
        group = parser.getgroup("general")
        group.addoption(
            '--build-dir', action="store", default=BUILD_PATH,
            help="Path to the build directory")
        group.addoption(
            '--run-xfail', action="store_true",
            help="If provided, tests marked as xfail will be run")

except ImportError:
    pytest = None


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


def _display_driver_logs(browser, driver):
    if browser == 'chrome':
        print('# Selenium browser logs')
        print(driver.get_log("browser"))
    elif browser == 'firefox':
        # browser logs are not available in GeckoDriver
        # https://github.com/mozilla/geckodriver/issues/284
        print('Accessing raw browser logs with Selenium is not '
              'supported by Firefox.')


class SeleniumWrapper:
    def __init__(self, server_port, server_hostname='127.0.0.1',
                 server_log=None, build_dir=None):
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        if build_dir is None:
            build_dir = BUILD_PATH

        driver = self.get_driver()
        wait = WebDriverWait(driver, timeout=40)
        if not (pathlib.Path(build_dir) / 'test.html').exists():
            # selenium does not expose HTTP response codes
            raise ValueError(f"{(build_dir / 'test.html').resolve()} "
                             f"does not exist!")
        driver.get(f'http://{server_hostname}:{server_port}/test.html')
        try:
            wait.until(PyodideInited())
        except TimeoutException:
            _display_driver_logs(self.browser, driver)
            raise TimeoutException()
        self.wait = wait
        self.driver = driver
        self.server_port = server_port
        self.server_hostname = server_hostname
        self.server_log = server_log

    @property
    def logs(self):
        logs = self.driver.execute_script("return window.logs")
        if logs is not None:
            return '\n'.join(str(x) for x in logs)
        else:
            return ""

    def clean_logs(self):
        self.driver.execute_script("window.logs = []")

    def run(self, code):
        return self.run_js(
            'return pyodide.runPython({!r})'.format(code))

    def run_async(self, code):
        from selenium.common.exceptions import TimeoutException
        self.run_js(
            """
            window.done = false;
            pyodide.runPythonAsync({!r})
              .then(function(output)
                      {{ window.output = output; window.error = false; }},
                    function(output)
                      {{ window.output = output; window.error = true; }})
              .finally(() => window.done = true);
            """.format(code)
        )
        try:
            self.wait.until(PackageLoaded())
        except TimeoutException:
            _display_driver_logs(self.browser, self.driver)
            print(self.logs)
            raise TimeoutException('runPythonAsync timed out')
        return self.run_js(
            """
            if (window.error) {
              throw window.output;
            }
            return window.output;
            """
        )

    def run_js(self, code):
        if isinstance(code, str) and code.startswith('\n'):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)
        catch = f"""
            Error.stackTraceLimit = Infinity;
            try {{ {code} }}
            catch (error) {{ console.log(error.stack); throw error; }}"""
        return self.driver.execute_script(catch)

    def setup_webworker(self):
        hostname = self.server_hostname
        port = self.server_port
        url = f'http://{hostname}:{port}/webworker_dev.js'
        self.run_js(
            f"""
            window.done = false;
            window.pyodideWorker = new Worker( '{url}' );

            window.pyodideWorker.onerror = function(e) {{
                window.output = e;
                window.error = true;
                window.done = true;
            }};

            window.pyodideWorker.onmessage = function(e) {{
              if (e.data.results) {{
                window.output = e.data.results;
                window.error = false;
              }} else {{
                window.output = e.data.error;
                window.error = true;
              }}
              window.done = true;
            }};
            """
        )

    def run_webworker(self, code):
        from selenium.common.exceptions import TimeoutException
        self.setup_webworker()
        if isinstance(code, str) and code.startswith('\n'):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)
        self.run_js(
            """
            var data = {{
              python: {!r}
            }};

            window.pyodideWorker.postMessage(data);
            """.format(code)
        )
        try:
            self.wait.until(PackageLoaded())
        except TimeoutException:
            _display_driver_logs(self.browser, self.driver)
            print(self.logs)
            raise TimeoutException('run_webworker timed out')
        return self.run_js(
            """
            if (window.error) {
                if (window.output instanceof Error) {
                    throw window.output;
                } else {
                    throw new Error(String(window.output))
                }
            }
            return window.output;
            """
        )

    def load_package(self, packages):
        self.run_js(
            'window.done = false\n' +
            'pyodide.loadPackage({!r})'.format(packages) +
            '.finally(function() { window.done = true; })')
        __tracebackhide__ = True
        self.wait_until_packages_loaded()

    def wait_until_packages_loaded(self):
        from selenium.common.exceptions import TimeoutException

        __tracebackhide__ = True
        try:
            self.wait.until(PackageLoaded())
        except TimeoutException:
            _display_driver_logs(self.browser, self.driver)
            print(self.logs)
            raise TimeoutException('wait_until_packages_loaded timed out')

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
            executable_path='geckodriver', options=options)


class ChromeWrapper(SeleniumWrapper):

    browser = 'chrome'

    def get_driver(self):
        from selenium.webdriver import Chrome
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import WebDriverException

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')

        self.JavascriptException = WebDriverException

        return Chrome(options=options)


if pytest is not None:
    @pytest.fixture(params=['firefox', 'chrome'])
    def selenium_standalone(request, web_server_main):
        server_hostname, server_port, server_log = web_server_main
        if request.param == 'firefox':
            cls = FirefoxWrapper
        elif request.param == 'chrome':
            cls = ChromeWrapper
        selenium = cls(build_dir=request.config.option.build_dir,
                       server_port=server_port,
                       server_hostname=server_hostname,
                       server_log=server_log)
        try:
            yield selenium
        finally:
            print(selenium.logs)
            selenium.driver.quit()

    @pytest.fixture(params=['firefox', 'chrome'], scope='module')
    def _selenium_cached(request, web_server_main):
        # Cached selenium instance. This is a copy-paste of
        # selenium_standalone to avoid fixture scope issues
        server_hostname, server_port, server_log = web_server_main
        if request.param == 'firefox':
            cls = FirefoxWrapper
        elif request.param == 'chrome':
            cls = ChromeWrapper
        selenium = cls(build_dir=request.config.option.build_dir,
                       server_port=server_port,
                       server_hostname=server_hostname,
                       server_log=server_log)
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


@pytest.fixture(scope='session')
def web_server_main(request):
    with spawn_web_server(request.config.option.build_dir) as output:
        yield output


@pytest.fixture(scope='session')
def web_server_secondary(request):
    with spawn_web_server(request.config.option.build_dir) as output:
        yield output


@contextlib.contextmanager
def spawn_web_server(build_dir=None):

    if build_dir is None:
        build_dir = BUILD_PATH

    tmp_dir = tempfile.mkdtemp()
    log_path = pathlib.Path(tmp_dir) / 'http-server.log'
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=run_web_server,
                                args=(q, log_path, build_dir))

    try:
        p.start()
        port = q.get()
        hostname = '127.0.0.1'

        print(f"Spawning webserver at http://{hostname}:{port} "
              f"(see logs in {log_path})")
        yield hostname, port, log_path
    finally:
        q.put("TERMINATE")
        p.join()
        shutil.rmtree(tmp_dir)


def run_web_server(q, log_filepath, build_dir):
    """Start the HTTP web server

    Parameters
    ----------
    q : Queue
      communication queue
    log_path : pathlib.Path
      path to the file where to store the logs
    """
    import http.server
    import socketserver

    os.chdir(build_dir)

    log_fh = log_filepath.open('w', buffering=1)
    sys.stdout = log_fh
    sys.stderr = log_fh

    class Handler(http.server.CGIHTTPRequestHandler):

        def translate_path(self, path):
            if path.startswith('/test/'):
                return TEST_PATH / path[6:]
            return super(Handler, self).translate_path(path)

        def is_cgi(self):
            if self.path.startswith('/test/') and self.path.endswith('.cgi'):
                self.cgi_info = '/test', self.path[6:]
                return True
            return False

        def log_message(self, format_, *args):
            print("[%s] source: %s:%s - %s"
                  % (self.log_date_time_string(),
                     *self.client_address,
                     format_ % args))

        def end_headers(self):
            # Enable Cross-Origin Resource Sharing (CORS)
            self.send_header('Access-Control-Allow-Origin', '*')
            super().end_headers()

    Handler.extensions_map['.wasm'] = 'application/wasm'

    with socketserver.TCPServer(("", 0), Handler) as httpd:
        host, port = httpd.server_address
        print(f"Starting webserver at http://{host}:{port}")
        httpd.server_name = 'test-server'
        httpd.server_port = port
        q.put(port)

        def service_actions():
            try:
                if q.get(False) == "TERMINATE":
                    print('Stopping server...')
                    sys.exit(0)
            except queue.Empty:
                pass

        httpd.service_actions = service_actions
        httpd.serve_forever()


if (__name__ == '__main__'
        and multiprocessing.current_process().name == 'MainProcess'
        and not hasattr(sys, "_pytest_session")):
    with spawn_web_server():
        # run forever
        while True:
            time.sleep(1)
