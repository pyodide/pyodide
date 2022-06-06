import contextlib

import pytest

from .browser import (
    BrowserWrapper,
    NodeWrapper,
    PlaywrightChromeWrapper,
    PlaywrightFirefoxWrapper,
    SeleniumChromeWrapper,
    SeleniumFirefoxWrapper,
)
from .server import spawn_web_server
from .utils import parse_driver_timeout, set_webdriver_script_timeout


@pytest.fixture(scope="module")
def playwright_browsers(request):
    if request.config.option.runner.lower() != "playwright":
        yield {}
    else:
        # import playwright here to allow running tests without playwright installation
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.exit(
                "playwright not installed. try `pip install playwright && python -m playwright install`",
                returncode=1,
            )

        with sync_playwright() as p:
            try:
                chromium = p.chromium.launch(
                    args=[
                        "--js-flags=--expose-gc",
                    ],
                )
                firefox = p.firefox.launch()
                # webkit = p.webkit.launch()
            except Exception as e:
                pytest.exit(f"playwright failed to launch\n{e}", returncode=1)
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


@contextlib.contextmanager
def selenium_common(
    request, web_server_main, load_pyodide=True, script_type="classic", browsers=None
):
    """Returns an initialized selenium object.

    If `_should_skip_test` indicate that the test will be skipped,
    return None, as initializing Pyodide for selenium is expensive
    """

    server_hostname, server_port, server_log = web_server_main
    runner_type = request.config.option.runner.lower()
    cls: type[BrowserWrapper]

    browser_set = {
        ("selenium", "firefox"): SeleniumFirefoxWrapper,
        ("selenium", "chrome"): SeleniumChromeWrapper,
        ("selenium", "node"): NodeWrapper,
        ("playwright", "firefox"): PlaywrightFirefoxWrapper,
        ("playwright", "chrome"): PlaywrightChromeWrapper,
        ("playwright", "node"): NodeWrapper,
    }

    cls = browser_set.get((runner_type, request.param))
    if cls is None:
        raise AssertionError(
            f"Unknown runner or browser: {runner_type} / {request.param}"
        )

    dist_dir = request.config.getoption("--dist-dir")
    runner = cls(
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
        browsers=browsers,
        script_type=script_type,
        dist_dir=dist_dir,
    )
    try:
        yield runner
    finally:
        runner.quit()


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone(request, web_server_main, playwright_browsers):
    with selenium_common(
        request, web_server_main, browsers=playwright_browsers
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(params=["firefox", "chrome", "node"], scope="module")
def selenium_esm(request, web_server_main, playwright_browsers):
    with selenium_common(
        request,
        web_server_main,
        load_pyodide=True,
        browsers=playwright_browsers,
        script_type="module",
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@contextlib.contextmanager
def selenium_standalone_noload_common(
    request, web_server_main, playwright_browsers, script_type="classic"
):
    with selenium_common(
        request,
        web_server_main,
        load_pyodide=False,
        browsers=playwright_browsers,
        script_type=script_type,
    ) as selenium:
        with set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            try:
                yield selenium
            finally:
                print(selenium.logs)


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def selenium_webworker_standalone(
    request, web_server_main, playwright_browsers, script_type
):
    # Avoid loading the fixture if the test is going to be skipped
    if request.param == "firefox" and script_type == "module":
        pytest.skip("firefox does not support module type web worker")

    with selenium_standalone_noload_common(
        request, web_server_main, playwright_browsers, script_type=script_type
    ) as selenium:
        yield selenium


@pytest.fixture(params=["firefox", "chrome", "node"], scope="function")
def selenium_standalone_noload(request, web_server_main, playwright_browsers):
    """Only difference between this and selenium_webworker_standalone is that
    this also tests on node."""

    with selenium_standalone_noload_common(
        request, web_server_main, playwright_browsers
    ) as selenium:
        yield selenium


# selenium instance cached at the module level
@pytest.fixture(params=["firefox", "chrome", "node"], scope="module")
def selenium_module_scope(request, web_server_main, playwright_browsers):
    with selenium_common(
        request, web_server_main, browsers=playwright_browsers
    ) as selenium:
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
            selenium, script_timeout=parse_driver_timeout(request.node)
        ):
            yield selenium


@pytest.fixture(params=["firefox", "chrome"], scope="function")
def console_html_fixture(request, web_server_main, playwright_browsers):
    with selenium_common(
        request, web_server_main, load_pyodide=False, browsers=playwright_browsers
    ) as selenium:
        selenium.goto(
            f"http://{selenium.server_hostname}:{selenium.server_port}/console.html"
        )
        selenium.javascript_setup()
        try:
            yield selenium
        finally:
            print(selenium.logs)


@pytest.fixture(scope="session")
def web_server_main(request):
    """Web server that serves files in the dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output


@pytest.fixture(scope="session")
def web_server_secondary(request):
    """Secondary web server that serves files dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output


@pytest.fixture(params=["classic", "module"], scope="module")
def script_type(request):
    return request.param
