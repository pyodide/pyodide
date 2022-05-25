import contextlib

import pytest

from .browser import ChromeWrapper, FirefoxWrapper, NodeWrapper, SeleniumWrapper
from .server import spawn_web_server
from .utils import parse_driver_timeout, set_webdriver_script_timeout


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

    dist_dir = request.config.getoption("--dist-dir")
    selenium = cls(
        server_port=server_port,
        server_hostname=server_hostname,
        server_log=server_log,
        load_pyodide=load_pyodide,
        script_type=script_type,
        dist_dir=dist_dir,
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


@pytest.fixture(params=["firefox", "chrome", "node"], scope="module")
def selenium_esm(request, web_server_main):
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
    """Web server that serves files in the dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output


@pytest.fixture(scope="session")
def web_server_secondary(request):
    """Secondary web server that serves files dist directory"""
    with spawn_web_server(request.config.option.dist_dir) as output:
        yield output
