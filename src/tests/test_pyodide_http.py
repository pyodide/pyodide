import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
def test_open_url(selenium, httpserver):
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
async def test_pyfetch_create_file(selenium):
    import pathlib

    from pyodide.http import pyfetch

    resp = await pyfetch("console.html")
    await resp._create_file("console.html")
    assert (
        pathlib.Path("/home/pyodide/console.html").read_text().find("fatal error.")
        > 3000
    )


@run_in_pyodide
async def test_pyfetch_unpack_archive(selenium):
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


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
def test_pyfetch_set_valid_credentials_value(selenium, httpserver):
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


@pytest.mark.xfail_browsers(
    node="XMLHttpRequest is not available in node",
    safari="raises TypeError: exceptions must derive from BaseException",
)
def test_pyfetch_coors_error(selenium, httpserver):
    httpserver.expect_request("/data").respond_with_data(
        b"HELLO",
        content_type="text/plain",
    )
    request_url = httpserver.url_for("/data")

    selenium.run_async(
        f"""
        import pyodide.http
        from unittest import TestCase
        raises = TestCase().assertRaises
        with raises(OSError):
            data = await pyodide.http.pyfetch('{request_url}')
        """
    )
