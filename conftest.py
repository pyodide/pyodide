"""
Various common utilities for testing.
"""

import contextlib
import json
import multiprocessing
import textwrap
import tempfile
import time
import os
import pathlib
import pexpect
import queue
import sys
import shutil

import pytest

ROOT_PATH = pathlib.Path(__file__).parents[0].resolve()
TEST_PATH = ROOT_PATH / "src" / "tests"
BUILD_PATH = ROOT_PATH / "build"

sys.path.append(str(ROOT_PATH / "pyodide-build"))
sys.path.append(str(ROOT_PATH / "src" / "py"))

from pyodide_build.testing import set_webdriver_script_timeout, parse_driver_timeout


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


def pytest_configure(config):
    """Monkey patch the function cwd_relative_nodeid

    returns the description of a test for the short summary table. Monkey patch
    it to reduce the verbosity of the test names in the table.  This leaves
    enough room to see the information about the test failure in the summary.
    """
    old_cwd_relative_nodeid = config.cwd_relative_nodeid

    def cwd_relative_nodeid(*args):
        result = old_cwd_relative_nodeid(*args)
        result = result.replace("src/tests/", "")
        result = result.replace("packages/", "")
        result = result.replace("::test_", "::")
        return result

    config.cwd_relative_nodeid = cwd_relative_nodeid


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
        self,
        server_port,
        server_hostname="127.0.0.1",
        server_log=None,
        load_pyodide=True,
        script_timeout=20,
    ):
        self.server_port = server_port
        self.server_hostname = server_hostname
        self.base_url = f"http://{self.server_hostname}:{self.server_port}"
        self.server_log = server_log
        self.driver = self.get_driver()
        self.set_script_timeout(script_timeout)
        self.script_timeout = script_timeout
        self.prepare_driver()
        self.javascript_setup()
        if load_pyodide:
            self.run_js(
                """
                let pyodide = await loadPyodide({ indexURL : './', fullStdLib: false, jsglobals : self });
                self.pyodide = pyodide;
                globalThis.pyodide = pyodide;
                pyodide._module.inTestHoist = true; // improve some error messages for tests
                pyodide.globals.get;
                pyodide.pyodide_py.eval_code;
                pyodide.pyodide_py.eval_code_async;
                pyodide.pyodide_py.register_js_module;
                pyodide.pyodide_py.unregister_js_module;
                pyodide.pyodide_py.find_imports;
                pyodide.runPython("");
                """,
            )
            self.save_state()
            self.restore_state()

    SETUP_CODE = pathlib.Path(ROOT_PATH / "tools/testsetup.js").read_text()

    def prepare_driver(self):
        self.driver.get(f"{self.base_url}/test.html")

    def set_script_timeout(self, timeout):
        self.driver.set_script_timeout(timeout)

    def quit(self):
        self.driver.quit()

    def refresh(self):
        self.driver.refresh()
        self.javascript_setup()

    def javascript_setup(self):
        self.run_js(
            SeleniumWrapper.SETUP_CODE,
            pyodide_checks=False,
        )

    @property
    def pyodide_loaded(self):
        return self.run_js("return !!(self.pyodide && self.pyodide.runPython);")

    @property
    def logs(self):
        logs = self.run_js("return self.logs;", pyodide_checks=False)
        if logs is not None:
            return "\n".join(str(x) for x in logs)
        return ""

    def clean_logs(self):
        self.run_js("self.logs = []", pyodide_checks=False)

    def run(self, code):
        return self.run_js(
            f"""
            let result = pyodide.runPython({code!r});
            if(result && result.toJs){{
                let converted_result = result.toJs();
                if(pyodide.isPyProxy(converted_result)){{
                    converted_result = undefined;
                }}
                result.destroy();
                return converted_result;
            }}
            return result;
            """
        )

    def run_async(self, code):
        return self.run_js(
            f"""
            await pyodide.loadPackagesFromImports({code!r})
            let result = await pyodide.runPythonAsync({code!r});
            if(result && result.toJs){{
                let converted_result = result.toJs();
                if(pyodide.isPyProxy(converted_result)){{
                    converted_result = undefined;
                }}
                result.destroy();
                return converted_result;
            }}
            return result;
            """
        )

    def run_js(self, code, pyodide_checks=True):
        """Run JavaScript code and check for pyodide errors"""
        if isinstance(code, str) and code.startswith("\n"):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)

        if pyodide_checks:
            check_code = """
                    if(globalThis.pyodide && pyodide._module && pyodide._module._PyErr_Occurred()){
                        try {
                            pyodide._module._pythonexc2js();
                        } catch(e){
                            console.error(`Python exited with error flag set! Error was:\n${e.message}`);
                            // Don't put original error message in new one: we want
                            // "pytest.raises(xxx, match=msg)" to fail
                            throw new Error(`Python exited with error flag set!`);
                        }
                    }
           """
        else:
            check_code = ""
        return self.run_js_inner(code, check_code)

    def run_js_inner(self, code, check_code):
        wrapper = """
            let cb = arguments[arguments.length - 1];
            let run = async () => { %s }
            (async () => {
                try {
                    let result = await run();
                    %s
                    cb([0, result]);
                } catch (e) {
                    cb([1, e.toString(), e.stack]);
                }
            })()
        """
        retval = self.driver.execute_async_script(wrapper % (code, check_code))
        if retval[0] == 0:
            return retval[1]
        else:
            raise JavascriptException(retval[1], retval[2])

    def get_num_hiwire_keys(self):
        return self.run_js("return pyodide._module.hiwire.num_keys();")

    @property
    def force_test_fail(self) -> bool:
        return self.run_js("return !!pyodide._module.fail_test;")

    def clear_force_test_fail(self):
        self.run_js("pyodide._module.fail_test = false;")

    def save_state(self):
        self.run_js("self.__savedState = pyodide._module.saveState();")

    def restore_state(self):
        self.run_js(
            """
            if(self.__savedState){
                pyodide._module.restoreState(self.__savedState)
            }
            """
        )

    def get_num_proxies(self):
        return self.run_js("return pyodide._module.pyproxy_alloc_map.size")

    def enable_pyproxy_tracing(self):
        self.run_js("pyodide._module.enable_pyproxy_allocation_tracing()")

    def disable_pyproxy_tracing(self):
        self.run_js("pyodide._module.disable_pyproxy_allocation_tracing()")

    def run_webworker(self, code):
        if isinstance(code, str) and code.startswith("\n"):
            # we have a multiline string, fix indentation
            code = textwrap.dedent(code)

        return self.run_js(
            """
            let worker = new Worker( '{}' );
            let res = new Promise((res, rej) => {{
                worker.onerror = e => rej(e);
                worker.onmessage = e => {{
                    if (e.data.results) {{
                       res(e.data.results);
                    }} else {{
                       rej(e.data.error);
                    }}
                }};
                worker.postMessage({{ python: {!r} }});
            }});
            return await res
            """.format(
                f"http://{self.server_hostname}:{self.server_port}/webworker_dev.js",
                code,
            ),
            pyodide_checks=False,
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
        options.add_argument("--js-flags=--expose-gc")
        return Chrome(options=options)

    def collect_garbage(self):
        self.driver.execute_cdp_cmd("HeapProfiler.collectGarbage", {})


class NodeWrapper(SeleniumWrapper):
    browser = "node"

    def init_node(self):
        os.chdir("build")
        self.p = pexpect.spawn(
            f"node --expose-gc ../tools/node_test_driver.js {self.base_url}", timeout=60
        )
        self.p.setecho(False)
        self.p.delaybeforesend = None
        os.chdir("..")

    def get_driver(self):
        self._logs = []
        self.init_node()

        class NodeDriver:
            def __getattr__(self, x):
                raise NotImplementedError()

        return NodeDriver()

    def prepare_driver(self):
        pass

    def set_script_timeout(self, timeout):
        self._timeout = timeout

    def quit(self):
        self.p.sendeof()

    def refresh(self):
        self.quit()
        self.init_node()
        self.javascript_setup()

    def collect_garbage(self):
        self.run_js("gc()")

    @property
    def logs(self):
        return "\n".join(self._logs)

    def clean_logs(self):
        self._logs = []

    def run_js_inner(self, code, check_code):
        check_code = ""
        wrapped = """
            let result = await (async () => { %s })();
            %s
            return result;
        """ % (
            code,
            check_code,
        )
        from uuid import uuid4

        cmd_id = str(uuid4())
        self.p.sendline(cmd_id)
        self.p.sendline(wrapped)
        self.p.sendline(cmd_id)
        self.p.expect_exact(f"{cmd_id}:UUID\r\n", timeout=self._timeout)
        self.p.expect_exact(f"{cmd_id}:UUID\r\n")
        if self.p.before:
            self._logs.append(self.p.before.decode()[:-2].replace("\r", ""))
        self.p.expect(f"[01]\r\n")
        success = int(self.p.match[0].decode()[0]) == 0
        self.p.expect_exact(f"\r\n{cmd_id}:UUID\r\n")
        if success:
            return json.loads(self.p.before.decode().replace("undefined", "null"))
        else:
            raise JavascriptException("", self.p.before.decode())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """We want to run extra verification at the start and end of each test to
    check that we haven't leaked memory. According to pytest issue #5044, it's
    not possible to "Fail" a test from a fixture (no matter what you do, pytest
    sets the test status to "Error"). The approach suggested there is hook
    pytest_runtest_call as we do here. To get access to the selenium fixture, we
    immitate the definition of pytest_pyfunc_call:
    https://github.com/pytest-dev/pytest/blob/6.2.2/src/_pytest/python.py#L177

    Pytest issue #5044:
    https://github.com/pytest-dev/pytest/issues/5044
    """
    selenium = None
    for fixture in item._fixtureinfo.argnames:
        if fixture.startswith("selenium"):
            selenium = item.funcargs[fixture]
            break
    if selenium and selenium.pyodide_loaded:
        trace_pyproxies = pytest.mark.skip_pyproxy_check.mark not in item.own_markers
        trace_hiwire_refs = (
            trace_pyproxies
            and pytest.mark.skip_refcount_check.mark not in item.own_markers
        )
        yield from extra_checks_test_wrapper(
            selenium, trace_hiwire_refs, trace_pyproxies
        )
    else:
        yield


def extra_checks_test_wrapper(selenium, trace_hiwire_refs, trace_pyproxies):
    """Extra conditions for test to pass:
    1. No explicit request for test to fail
    2. No leaked JsRefs
    3. No leaked PyProxys
    """
    selenium.clear_force_test_fail()
    init_num_keys = selenium.get_num_hiwire_keys()
    if trace_pyproxies:
        selenium.enable_pyproxy_tracing()
        init_num_proxies = selenium.get_num_proxies()
    a = yield
    try:
        # If these guys cause a crash because the test really screwed things up,
        # we override the error message with the better message returned by
        # a.result() in the finally block.
        selenium.disable_pyproxy_tracing()
        selenium.restore_state()
    finally:
        # if there was an error in the body of the test, flush it out by calling
        # get_result (we don't want to override the error message by raising a
        # different error here.)
        a.get_result()
    if selenium.force_test_fail:
        raise Exception("Test failure explicitly requested but no error was raised.")
    if trace_pyproxies and trace_hiwire_refs:
        delta_proxies = selenium.get_num_proxies() - init_num_proxies
        delta_keys = selenium.get_num_hiwire_keys() - init_num_keys
        assert (delta_proxies, delta_keys) == (0, 0) or delta_keys < 0
    if trace_hiwire_refs:
        delta_keys = selenium.get_num_hiwire_keys() - init_num_keys
        assert delta_keys <= 0


@contextlib.contextmanager
def selenium_common(request, web_server_main, load_pyodide=True):
    server_hostname, server_port, server_log = web_server_main
    if request.param == "firefox":
        cls = FirefoxWrapper
    elif request.param == "chrome":
        cls = ChromeWrapper
    elif request.param == "node":
        cls = NodeWrapper
    else:
        assert False
    selenium = cls(
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
    )
    try:
        yield selenium
    finally:
        selenium.quit()


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone(request, web_server_main):
    with selenium_common(request, web_server_main) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@contextlib.contextmanager
def selenium_standalone_noload_common(request, web_server_main):
    with selenium_common(request, web_server_main, load_pyodide=False) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def selenium_webworker_standalone(request, web_server_main):
    with selenium_standalone_noload_common(request, web_server_main) as selenium:
        yield selenium


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone_noload(request, web_server_main):
    """Only difference between this and selenium_webworker_standalone is that
    this also tests on node."""
    with selenium_standalone_noload_common(request, web_server_main) as selenium:
        yield selenium


# selenium instance cached at the module level
@pytest.fixture(params=["firefox", "chrome", "node"], scope="module")
def selenium_module_scope(request, web_server_main):
    with selenium_common(request, web_server_main) as selenium:
        yield selenium


# Hypothesis is unhappy with function scope fixtures. Instead, use the
# module scope fixture `selenium_module_scope` and use:
# `with selenium_context_manager(selenium_module_scope) as selenium`
@contextlib.contextmanager
def selenium_context_manager(selenium_module_scope):
    try:
        selenium_module_scope.clean_logs()
        yield selenium_module_scope
    finally:
        print(selenium_module_scope.logs)


@pytest.fixture
def selenium(request, selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            yield selenium


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
