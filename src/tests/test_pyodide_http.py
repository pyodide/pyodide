import pytest
from pyodide_test_runner import run_in_pyodide


def test_open_url(selenium, httpserver):
    if selenium.browser == "node":
        pytest.xfail("XMLHttpRequest not available in node")
    httpserver.expect_request("/data").respond_with_data(
        b"HELLO", content_type="text/text", headers={"Access-Control-Allow-Origin": "*"}
    )
    request_url = httpserver.url_for("/data")

    assert (
        selenium.run(
            f"""
        import pyodide
        pyodide.open_url('{request_url}').read()
        """
        )
        == "HELLO"
    )


@run_in_pyodide
async def test_pyfetch_create_file():
    import pathlib

    from pyodide.http import pyfetch

    resp = await pyfetch("console.html")
    await resp._create_file("console.html")
    assert (
        pathlib.Path("/home/pyodide/console.html").read_text().find("fatal error.")
        > 3000
    )


@run_in_pyodide
async def test_pyfetch_unpack_archive():
    import pathlib

    from pyodide.http import pyfetch

    resp = await pyfetch(
        "https://files.pythonhosted.org/packages/93/8d/e1e98360dc899e533cb3dd857494f2571b129bdffcee76365009b2bb507c/example_pypi_package-0.1.0.tar.gz"
    )
    await resp.unpack_archive()
    names = [
        f.stem
        for f in pathlib.Path("/home/pyodide/example_pypi_package-0.1.0").glob("*")
    ]
    assert names == [
        "LICENSE",
        "MANIFEST",
        "PKG-INFO",
        "README",
        "pyproject",
        "setup",
        "setup",
        "src",
        "tests",
    ]


def test_pyfetch_set_valid_credentials_value(selenium, httpserver):
    if selenium.browser == "node":
        pytest.xfail("XMLHttpRequest not available in node")
    httpserver.expect_request("/data").respond_with_data(
        b"HELLO",
        content_type="text/plain",
        headers={"Access-Control-Allow-Origin": "*"},
    )
    request_url = httpserver.url_for("/data")

    assert (
        selenium.run_async(
            f"""
        import pyodide.http
        data = await pyodide.http.pyfetch('{request_url}', credentials='omit')
        data.string()
        """
        )
        == "HELLO"
    )
