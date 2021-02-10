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
TEST_PATH = ROOT_PATH / "src" / "tests"
BUILD_PATH = ROOT_PATH / "build"

sys.path.append(str(ROOT_PATH))

from pyodide_build._fixes import _selenium_is_connectable  # noqa: E402
import selenium.webdriver.common.utils  # noqa: E402

# XXX: Temporary fix for ConnectionError in selenium

selenium.webdriver.common.utils.is_connectable = _selenium_is_connectable

try:
    import pytest

    def pytest_addoption(parser):
        group = parser.getgroup("general")
        group.addoption(
            "--build-dir",
            action="store",
            default=BUILD_PATH,
            help="Path to the build directory",
        )
        group.addoption(
            "--run-xfail",
            action="store_true",
            help="If provided, tests marked as xfail will be run",
        )


except ImportError:
    pytest = None  # type: ignore


class JavascriptException(Exception):
    def __init__(self, msg, stack):
        self.msg = msg
        self.stack = stack
        # In chrome the stack contains the message
        if self.stack and self.stack.startswith(self.msg):
            self.msg = ""

    def __str__(self):
        return "\n\n".join(x for x in [self.msg, self.stack] if x)


class SeleniumWrapper:
    JavascriptException = JavascriptException

    def __init__(
        self, server_port, server_hostname="127.0.0.1", server_log=None, build_dir=None
    ):
        if build_dir is None:
            build_dir = BUILD_PATH

        self.driver = self.get_driver()
        self.server_port = server_port
        self.server_hostname = server_hostname
        self.server_log = server_log

        if not (pathlib.Path(build_dir) / "test.html").exists():
            # selenium does not expose HTTP response codes
            raise ValueError(
                f"{(build_dir / 'test.html').resolve()} " f"does not exist!"
            )
        self.driver.get(f"http://{server_hostname}:{server_port}/test.html")
        self.run_js("Error.stackTraceLimit = Infinity")
        self.run_js("await languagePluginLoader")

    @property
    def logs(self):
        logs = self.driver.execute_script("return window.logs")
        if logs is not None:
            return "\n".join(str(x) for x in logs)
        else:
            return ""

    def clean_logs(self):
        self.driver.execute_script("window.logs = []")

    def run(self, code):
        return self.run_js(
            f"""
            let result = pyodide.runPython({code!r});
            if(result && result.deepCopyToJavascript){{
                let converted_result = result.deepCopyToJavascript();
                result.destroy();
                return converted_result;
            }}
            return result;
            """
        )

    def run_async(self, code):
        return self.run_js(
            f"""
            let result = await pyodide.runPythonAsync({code!r});
            if(result && result.deepCopyToJavascript){{
                let converted_result = result.deepCopyToJavascript();
                result.destroy();
                return converted_result;
            }}
            return result;
            """
        )

    def run_js(self, code):
        if isinstance(code, str) and code.startswith("\n"):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)

        wrapper = """
            let cb = arguments[arguments.length - 1];
            let run = async () => { %s }
            (async () => {
                try {
                    let result = await run();
                    if(pyodide && pyodide._module && pyodide._module._PyErr_Occurred()){
                        try {
                            pyodide._module._pythonexc2js();
                        } catch(e){
                            console.error(`Python exited with error flag set! Error was:\n{e.message}`);
                            // Don't put original error message in new one: we want
                            // "pytest.raises(xxx, match=msg)" to fail
                            throw new Error(`Python exited with error flag set!`);
                        }
                    }
                    cb([0, result]);
                } catch (e) {
                    cb([1, e.toString(), e.stack]);
                }
            })()
        """

        retval = self.driver.execute_async_script(wrapper % code)

        if retval[0] == 0:
            return retval[1]
        else:
            raise JavascriptException(retval[1], retval[2])

    def run_webworker(self, code):
        if isinstance(code, str) and code.startswith("\n"):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)

        return self.run_js(
            """
            let worker = new Worker( '{}' );
            worker.postMessage({{ python: {!r} }});
            return new Promise((res, rej) => {{
                worker.onerror = e => rej(e);
                worker.onmessage = e => {{
                    if (e.data.results) {{
                       res(e.data.results);
                    }} else {{
                       rej(e.data.error);
                    }}
                }};
            }})
            """.format(
                f"http://{self.server_hostname}:{self.server_port}/webworker_dev.js",
                code,
            )
        )

    def load_package(self, packages):
        self.run_js("await pyodide.loadPackage({!r})".format(packages))

    @property
    def urls(self):
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            yield self.driver.current_url


class FirefoxWrapper(SeleniumWrapper):

    browser = "firefox"

    def get_driver(self):
        from selenium.webdriver import Firefox
        from selenium.webdriver.firefox.options import Options

        options = Options()
        options.add_argument("-headless")

        return Firefox(executable_path="geckodriver", options=options)


class ChromeWrapper(SeleniumWrapper):

    browser = "chrome"

    def get_driver(self):
        from selenium.webdriver import Chrome
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")

        return Chrome(options=options)


if pytest is not None:

    @pytest.fixture(params=["firefox", "chrome"])
    def selenium_standalone(request, web_server_main):
        server_hostname, server_port, server_log = web_server_main
        if request.param == "firefox":
            cls = FirefoxWrapper
        elif request.param == "chrome":
            cls = ChromeWrapper
        selenium = cls(
            build_dir=request.config.option.build_dir,
            server_port=server_port,
            server_hostname=server_hostname,
            server_log=server_log,
        )
        try:
            yield selenium
        finally:
            print(selenium.logs)
            selenium.driver.quit()

    @pytest.fixture(params=["firefox", "chrome"], scope="module")
    def _selenium_cached(request, web_server_main):
        # Cached selenium instance. This is a copy-paste of
        # selenium_standalone to avoid fixture scope issues
        server_hostname, server_port, server_log = web_server_main
        if request.param == "firefox":
            cls = FirefoxWrapper
        elif request.param == "chrome":
            cls = ChromeWrapper
        selenium = cls(
            build_dir=request.config.option.build_dir,
            server_port=server_port,
            server_hostname=server_hostname,
            server_log=server_log,
        )
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


@pytest.fixture(scope="session")
def web_server_main(request):
    """Web server that serves files in the build/ directory"""
    with spawn_web_server(request.config.option.build_dir) as output:
        yield output


@pytest.fixture(scope="session")
def web_server_secondary(request):
    """Secondary web server that serves files build/ directory"""
    with spawn_web_server(request.config.option.build_dir) as output:
        yield output


@pytest.fixture(scope="session")
def web_server_tst_data(request):
    """Web server that serves files in the src/tests/data/ directory"""
    with spawn_web_server(TEST_PATH / "data") as output:
        yield output


@contextlib.contextmanager
def spawn_web_server(build_dir=None):

    if build_dir is None:
        build_dir = BUILD_PATH

    tmp_dir = tempfile.mkdtemp()
    log_path = pathlib.Path(tmp_dir) / "http-server.log"
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=run_web_server, args=(q, log_path, build_dir))

    try:
        p.start()
        port = q.get()
        hostname = "127.0.0.1"

        print(
            f"Spawning webserver at http://{hostname}:{port} "
            f"(see logs in {log_path})"
        )
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

    log_fh = log_filepath.open("w", buffering=1)
    sys.stdout = log_fh
    sys.stderr = log_fh

    test_prefix = "/src/tests/"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format_, *args):
            print(
                "[%s] source: %s:%s - %s"
                % (self.log_date_time_string(), *self.client_address, format_ % args)
            )

        def end_headers(self):
            # Enable Cross-Origin Resource Sharing (CORS)
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

    with socketserver.TCPServer(("", 0), Handler) as httpd:
        host, port = httpd.server_address
        print(f"Starting webserver at http://{host}:{port}")
        httpd.server_name = "test-server"
        httpd.server_port = port
        q.put(port)

        def service_actions():
            try:
                if q.get(False) == "TERMINATE":
                    print("Stopping server...")
                    sys.exit(0)
            except queue.Empty:
                pass

        httpd.service_actions = service_actions
        httpd.serve_forever()


if (
    __name__ == "__main__"
    and multiprocessing.current_process().name == "MainProcess"
    and not hasattr(sys, "_pytest_session")
):
    with spawn_web_server():
        # run forever
        while True:
            time.sleep(1)
