"""
Various common utilities for testing.
"""
import contextlib
import functools
import json
import multiprocessing
import os
import pathlib
import queue
import re
import shutil
import sys
import tempfile
import textwrap
import time

import pexpect
import pytest

ROOT_PATH = pathlib.Path(__file__).parents[0].resolve()
TEST_PATH = ROOT_PATH / "src" / "tests"
BUILD_PATH = ROOT_PATH / "build"

sys.path.append(str(ROOT_PATH / "pyodide-build"))
sys.path.append(str(ROOT_PATH / "src" / "py"))

from pyodide_build.testing import parse_driver_timeout, set_webdriver_script_timeout


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


def pytest_collection_modifyitems(config, items):
    """Called after collect is completed.
    Parameters
    ----------
    config : pytest config
    items : list of collected items
    """
    for item in items:
        _maybe_skip_test(item, delayed=True)


@functools.cache
def built_packages() -> list[str]:
    """Returns the list of built package names from packages.json"""
    packages_json_path = BUILD_PATH / "packages.json"
    if not packages_json_path.exists():
        return []
    return list(json.loads(packages_json_path.read_text())["packages"].keys())


def _package_is_built(package_name: str) -> bool:
    return package_name in built_packages()


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
        script_type="classic",
    ):
        self.server_port = server_port
        self.server_hostname = server_hostname
        self.base_url = f"http://{self.server_hostname}:{self.server_port}"
        self.server_log = server_log
        self.script_type = script_type
        self.driver = self.get_driver()  # type: ignore[attr-defined]
        self.set_script_timeout(script_timeout)
        self.script_timeout = script_timeout
        self.prepare_driver()
        self.javascript_setup()
        if load_pyodide:
            self.load_pyodide()
            self.initialize_global_hiwire_objects()
            self.save_state()
            self.restore_state()

    SETUP_CODE = pathlib.Path(ROOT_PATH / "tools/testsetup.js").read_text()

    def prepare_driver(self):
        if self.script_type == "classic":
            self.driver.get(f"{self.base_url}/test.html")
        elif self.script_type == "module":
            self.driver.get(f"{self.base_url}/module_test.html")
        else:
            raise Exception("Unknown script type to load!")

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

    def load_pyodide(self):
        self.run_js(
            """
            let pyodide = await loadPyodide({ fullStdLib: false, jsglobals : self });
            self.pyodide = pyodide;
            globalThis.pyodide = pyodide;
            pyodide._api.inTestHoist = true; // improve some error messages for tests
            """
        )

    def initialize_global_hiwire_objects(self):
        """
        There are a bunch of global objects that occasionally enter the hiwire cache
        but never leave. The refcount checks get angry about them if they aren't preloaded.
        We need to go through and touch them all once to keep everything okay.
        """
        self.run_js(
            """
            pyodide.globals.get;
            pyodide.pyodide_py.eval_code;
            pyodide.pyodide_py.eval_code_async;
            pyodide.pyodide_py.register_js_module;
            pyodide.pyodide_py.unregister_js_module;
            pyodide.pyodide_py.find_imports;
            pyodide._api.importlib.invalidate_caches;
            pyodide._api.package_loader.unpack_buffer;
            pyodide._api.package_loader.get_dynlibs;
            pyodide._api._util_module = pyodide.pyimport("pyodide._util");
            pyodide._api._util_module.unpack_buffer_archive;
            pyodide.runPython("");
            """
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
                    cb([1, e.toString(), e.stack, e.message]);
                }
            })()
        """
        retval = self.driver.execute_async_script(wrapper % (code, check_code))
        if retval[0] == 0:
            return retval[1]
        else:
            print("JavascriptException message: ", retval[3])
            raise JavascriptException(retval[1], retval[2])

    def get_num_hiwire_keys(self):
        return self.run_js("return pyodide._module.hiwire.num_keys();")

    @property
    def force_test_fail(self) -> bool:
        return self.run_js("return !!pyodide._api.fail_test;")

    def clear_force_test_fail(self):
        self.run_js("pyodide._api.fail_test = false;")

    def save_state(self):
        self.run_js("self.__savedState = pyodide._api.saveState();")

    def restore_state(self):
        self.run_js(
            """
            if(self.__savedState){
                pyodide._api.restoreState(self.__savedState)
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

        worker_file = (
            "webworker_dev.js"
            if self.script_type == "classic"
            else "module_webworker_dev.js"
        )

        return self.run_js(
            """
            let worker = new Worker('{}', {{ type: '{}' }});
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
                f"http://{self.server_hostname}:{self.server_port}/{worker_file}",
                self.script_type,
                code,
            ),
            pyodide_checks=False,
        )

    def load_package(self, packages):
        self.run_js(f"await pyodide.loadPackage({packages!r})")

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
        options.add_argument("--headless")

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
            let result = await (async () => {{ {} }})();
            {}
            return result;
        """.format(
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
        self.p.expect("[01]\r\n")
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
    imitate the definition of pytest_pyfunc_call:
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


def _maybe_skip_test(item, delayed=False):
    """If necessary skip test at the fixture level, to avoid

    loading the selenium_standalone fixture which takes a long time.
    """
    skip_msg = None
    # Testing a package. Skip the test if the package is not built.
    match = re.match(
        r".*/packages/(?P<name>[\w\-]+)/test_[\w\-]+\.py", str(item.parent.fspath)
    )
    if match:
        package_name = match.group("name")
        if not _package_is_built(package_name):
            skip_msg = f"package '{package_name}' is not built."

    # Common package import test. Skip it if the package is not built.
    if (
        skip_msg is None
        and str(item.fspath).endswith("test_packages_common.py")
        and item.name.startswith("test_import")
    ):
        match = re.match(
            r"test_import\[(firefox|chrome|node)-(?P<name>[\w-]+)\]", item.name
        )
        if match:
            package_name = match.group("name")
            if not _package_is_built(package_name):
                # If the test is going to be skipped remove the
                # selenium_standalone as it takes a long time to initialize
                skip_msg = f"package '{package_name}' is not built."
        else:
            raise AssertionError(
                f"Couldn't parse package name from {item.name}. This should not happen!"
            )

    # TODO: also use this hook to skip doctests we cannot run (or run them
    # inside the selenium wrapper)

    if skip_msg is not None:
        if delayed:
            item.add_marker(pytest.mark.skip(reason=skip_msg))
        else:
            pytest.skip(skip_msg)


@contextlib.contextmanager
def selenium_common(request, web_server_main, load_pyodide=True, script_type="classic"):
    """Returns an initialized selenium object.

    If `_should_skip_test` indicate that the test will be skipped,
    return None, as initializing Pyodide for selenium is expensive
    """

    server_hostname, server_port, server_log = web_server_main
    cls: type[SeleniumWrapper]
    if request.param == "firefox":
        cls = FirefoxWrapper
    elif request.param == "chrome":
        cls = ChromeWrapper
    elif request.param == "node":
        cls = NodeWrapper
    else:
        raise AssertionError(f"Unknown browser: {request.param}")
    selenium = cls(
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
        script_type=script_type,
    )
    try:
        yield selenium
    finally:
        selenium.quit()


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone(request, web_server_main):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with selenium_common(request, web_server_main) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(params=["firefox", "chrome", "node"], scope="module")
def selenium_esm(request, web_server_main):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with selenium_common(
        request, web_server_main, load_pyodide=True, script_type="module"
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@contextlib.contextmanager
def selenium_standalone_noload_common(request, web_server_main, script_type="classic"):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with selenium_common(
        request, web_server_main, load_pyodide=False, script_type=script_type
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def selenium_webworker_standalone(request, web_server_main, script_type):
    # Avoid loading the fixture if the test is going to be skipped
    if request.param == "firefox" and script_type == "module":
        pytest.skip("firefox does not support module type web worker")
    _maybe_skip_test(request.node)
    with selenium_standalone_noload_common(
        request, web_server_main, script_type=script_type
    ) as selenium:
        yield selenium


@pytest.fixture(params=["classic", "module"], scope="module")
def script_type(request):
    return request.param


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone_noload(request, web_server_main):
    """Only difference between this and selenium_webworker_standalone is that
    this also tests on node."""
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)
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
    q: multiprocessing.Queue[str] = multiprocessing.Queue()
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
        httpd.server_name = "test-server"  # type: ignore[attr-defined]
        httpd.server_port = port  # type: ignore[attr-defined]
        q.put(port)

        def service_actions():
            try:
                if q.get(False) == "TERMINATE":
                    print("Stopping server...")
                    sys.exit(0)
            except queue.Empty:
                pass

        httpd.service_actions = service_actions  # type: ignore[assignment]
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
