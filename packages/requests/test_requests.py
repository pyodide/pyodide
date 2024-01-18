import pytest
from pytest_pyodide import run_in_pyodide

# absolutely totally basic test that requests works
#
# requests depends on urllib3, so fails here may actually be fails in
# urllib3


@pytest.mark.xfail_browsers(node="synchronous http not supported in node yet")
@run_in_pyodide(packages=["requests"])
def test_requests_basic(selenium_standalone):
    import requests

    import js

    our_url = js.window.location
    r = requests.get(our_url)
    assert r.status_code == 200
    txt = r.text
    assert isinstance(txt, str)
    assert len(r.text) > 0
