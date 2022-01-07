import re
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

from conftest import (
    ROOT_PATH,
    TEST_PATH,
    BUILD_PATH,
    _maybe_skip_test,
    JavascriptException,
)

from pyodide_build.testing import set_webdriver_script_timeout, parse_driver_timeout


@pytest.fixture(scope="session")
def playwright_browsers(request):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch(
            args=[
                "--js-flags=--expose-gc",
            ],
        )
        firefox = p.firefox.launch()
        # webkit = p.webkit.launch()
        try:
            yield {
                "chrome": chromium,
                "firefox": firefox,
                # "webkit": webkit,
            }
        finally:
            chromium.close()
            firefox.close()
            # webkit.close()


class PlaywrightWrapper:
    browser = ""
    JavascriptException = JavascriptException
    SETUP_CODE = pathlib.Path(ROOT_PATH / "tools/testsetup.js").read_text()  # type: ignore

    def __init__(
        self,
        server_port,
        server_hostname="127.0.0.1",
        server_log=None,
        load_pyodide=True,
        browsers=None,
        script_timeout=20000,
    ):
        self.server_port = server_port
        self.server_hostname = server_hostname
        self.base_url = f"http://{self.server_hostname}:{self.server_port}"
        self.server_log = server_log
        self.browsers = browsers

        self.driver = self.get_driver()
        self.set_script_timeout(script_timeout)
        self.script_timeout = script_timeout
        self.prepare()
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
                pyodide._module._util_module = pyodide.pyimport("pyodide._util");
                pyodide._module._util_module.unpack_buffer_archive;
                pyodide._module.importlib.invalidate_caches;
                pyodide.runPython("");
                """,
            )
            self.save_state()
            self.restore_state()

    def get_driver(self):
        return self.browsers[self.browser].new_page()

    def prepare(self):
        self.driver.goto(f"{self.base_url}/test.html")

    def set_script_timeout(self, timeout):
        self.driver.set_default_timeout(timeout)

    def quit(self):
        self.driver.close()

    def refresh(self):
        self.driver.reload()
        self.javascript_setup()

    def javascript_setup(self):
        self.run_js(
            self.SETUP_CODE,
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
        # playwright `evaluate` waits until primise to resolve,
        # so we don't need to use a callback like selenium.
        wrapper = """
            let run = async () => { %s }
            (async () => {
                try {
                    let result = await run();
                    %s
                    return [0, result];
                } catch (e) {
                    return [1, e.toString(), e.stack];
                }
            })()
        """
        retval = self.driver.evaluate(wrapper % (code, check_code))
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


class ChromePlaywrightWrapper(PlaywrightWrapper):
    browser = "chrome"

    def collect_garbage(self):
        client = self.driver.context.new_cdp_session(self.driver)
        client.send("HeapProfiler.collectGarbage")


class FirefoxPlaywrightWrapper(PlaywrightWrapper):
    browser = "firefox"


@contextlib.contextmanager
def playwright_common(
    browser,
    playwright_browsers,
    web_server_main,
    load_pyodide=True,
):
    """Returns an initialized playwright page object"""

    server_hostname, server_port, server_log = web_server_main
    if browser == "firefox":
        cls = FirefoxPlaywrightWrapper
    elif browser == "chrome":
        cls = ChromePlaywrightWrapper
    else:
        assert False

    playwright = cls(
        browsers=playwright_browsers,
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
    )

    try:
        yield playwright
    finally:
        playwright.quit()


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def playwright_standalone(request, playwright_browsers, web_server_main):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with playwright_common(
        request.param, playwright_browsers, web_server_main
    ) as playwright:
        with set_webdriver_script_timeout(
            playwright, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield playwright
            finally:
                print(playwright.logs)


# playwright instance cached at the module level
@pytest.fixture(params=["firefox", "chrome"], scope="module")
def playwright_module_scope(request, playwright_browsers, web_server_main):
    with playwright_common(
        request.param, playwright_browsers, web_server_main
    ) as playwright:
        yield playwright


# Hypothesis is unhappy with function scope fixtures. Instead, use the
# module scope fixture `playwright_module_scope` and use:
# `with playwright_context_manager(playwright_module_scope) as playwright`
@contextlib.contextmanager
def playwright_context_manager(playwright_module_scope):
    try:
        playwright_module_scope.clean_logs()
        yield playwright_module_scope
    finally:
        print(playwright_module_scope.logs)


@pytest.fixture
def playwright(request, playwright_module_scope):
    with playwright_context_manager(playwright_module_scope) as playwright:
        with set_webdriver_script_timeout(
            playwright, script_timeout=parse_driver_timeout(request)
        ):
            yield playwright


@contextlib.contextmanager
def playwright_noload_common(request, playwright_browsers, web_server_main):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with playwright_common(
        request.param, playwright_browsers, web_server_main, load_pyodide=False
    ) as playwright:
        with set_webdriver_script_timeout(
            playwright, script_timeout=parse_driver_timeout(request)
        ):
            try:
                yield playwright
            finally:
                print(playwright.logs)


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def playwright_webworker(request, playwright_browsers, web_server_main):
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with playwright_noload_common(
        request, playwright_browsers, web_server_main
    ) as playwright:
        yield playwright


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def playwright_noload(request, playwright_browsers, web_server_main):
    """Only difference between this and `playwright` fixture is that this also tests on node."""
    # Avoid loading the fixture if the test is going to be skipped
    _maybe_skip_test(request.node)

    with playwright_noload_common(
        request, playwright_browsers, web_server_main
    ) as playwright:
        yield playwright


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def playwright_console_html_fixture(request, playwright_browsers, web_server_main):
    with playwright_common(
        request.param, playwright_browsers, web_server_main, False
    ) as playwright:
        playwright.driver.goto(
            f"http://{playwright.server_hostname}:{playwright.server_port}/console.html"
        )
        playwright.javascript_setup()
        try:
            yield playwright
        finally:
            print(playwright.logs)
