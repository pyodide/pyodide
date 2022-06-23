"""
Various common utilities for testing.
"""
import pathlib
import sys

import pytest

ROOT_PATH = pathlib.Path(__file__).parents[0].resolve()
DIST_PATH = ROOT_PATH / "dist"

sys.path.append(str(ROOT_PATH / "pyodide-build"))
sys.path.append(str(ROOT_PATH / "src" / "py"))

from pyodide_test_runner.utils import maybe_skip_test
from pyodide_test_runner.utils import package_is_built as _package_is_built
from pyodide_test_runner.utils import parse_xfail_browsers


def pytest_addoption(parser):
    group = parser.getgroup("general")
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
    global CONFIG

    old_cwd_relative_nodeid = config.cwd_relative_nodeid

    def cwd_relative_nodeid(*args):
        result = old_cwd_relative_nodeid(*args)
        result = result.replace("src/tests/", "")
        result = result.replace("packages/", "")
        result = result.replace("::test_", "::")
        return result

    config.cwd_relative_nodeid = cwd_relative_nodeid

    pytest.pyodide_dist_dir = config.getoption("--dist-dir")


def pytest_collection_modifyitems(config, items):
    """Called after collect is completed.
    Parameters
    ----------
    config : pytest config
    items : list of collected items
    """
    for item in items:
        maybe_skip_test(item, config.getoption("--dist-dir"), delayed=True)


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
    browser = None
    for fixture in item._fixtureinfo.argnames:
        if fixture.startswith("selenium"):
            browser = item.funcargs[fixture]
            break

    if not browser:
        yield
        return

    xfail_msg = parse_xfail_browsers(item).get(browser.browser, None)
    if xfail_msg is not None:
        pytest.xfail(xfail_msg)

    if not browser.pyodide_loaded:
        yield
        return

    trace_pyproxies = pytest.mark.skip_pyproxy_check.mark not in item.own_markers
    trace_hiwire_refs = (
        trace_pyproxies and pytest.mark.skip_refcount_check.mark not in item.own_markers
    )
    yield from extra_checks_test_wrapper(browser, trace_hiwire_refs, trace_pyproxies)


def extra_checks_test_wrapper(browser, trace_hiwire_refs, trace_pyproxies):
    """Extra conditions for test to pass:
    1. No explicit request for test to fail
    2. No leaked JsRefs
    3. No leaked PyProxys
    """
    browser.clear_force_test_fail()
    init_num_keys = browser.get_num_hiwire_keys()
    if trace_pyproxies:
        browser.enable_pyproxy_tracing()
        init_num_proxies = browser.get_num_proxies()
    a = yield
    try:
        # If these guys cause a crash because the test really screwed things up,
        # we override the error message with the better message returned by
        # a.result() in the finally block.
        browser.disable_pyproxy_tracing()
        browser.restore_state()
    finally:
        # if there was an error in the body of the test, flush it out by calling
        # get_result (we don't want to override the error message by raising a
        # different error here.)
        a.get_result()
    if browser.force_test_fail:
        raise Exception("Test failure explicitly requested but no error was raised.")
    if trace_pyproxies and trace_hiwire_refs:
        delta_proxies = browser.get_num_proxies() - init_num_proxies
        delta_keys = browser.get_num_hiwire_keys() - init_num_keys
        assert (delta_proxies, delta_keys) == (0, 0) or delta_keys < 0
    if trace_hiwire_refs:
        delta_keys = browser.get_num_hiwire_keys() - init_num_keys
        assert delta_keys <= 0


def package_is_built(package_name):
    return _package_is_built(package_name, pytest.pyodide_dist_dir)
