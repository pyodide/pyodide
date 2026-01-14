import pytest
from pytest_pyodide import run_in_pyodide


# Absolutely totally basic test that urllib3 works at all.
#
# requests depends on urllib3, so fails here will kill requests also.
#
# n.b. urllib officially supports emscripten, so the test suite there does pretty
# thorough testing - this is just to check it runs on the current build of pyodide
# and we haven't broken anything on our side
@pytest.mark.xfail_browsers(node="synchronous http not supported in node yet")
@run_in_pyodide(packages=["urllib3"])
def test_requests_basic(selenium_standalone):
    import urllib3

    import js

    our_url = str(js.window.location)
    resp = urllib3.request("GET", our_url)
    assert resp.status == 200
    txt = resp.data.decode()
    assert isinstance(txt, str)
    assert len(txt) > 0
