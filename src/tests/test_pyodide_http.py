import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture
def url_notfound(httpserver):
    httpserver.expect_oneshot_request("/url_notfound").respond_with_data(
        b"404 Not Found",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=404,
    )
    return httpserver.url_for("/url_notfound")


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
def test_open_url(selenium, httpserver):
    httpserver.expect_oneshot_request("/test_open_url").respond_with_data(
        b"HELLO", content_type="text/text", headers={"Access-Control-Allow-Origin": "*"}
    )
    request_url = httpserver.url_for("/test_open_url")

    assert (
        selenium.run(
            f"""
            from pyodide.http import open_url
            open_url('{request_url}').read()
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
async def test_pyfetch_return_400_status_body(selenium, url_notfound):
    from pyodide.http import pyfetch

    resp = await pyfetch(url_notfound)
    body = await resp.string()
    assert body == "404 Not Found"


@pytest.fixture
def raise_for_status_fixture(httpserver):
    httpserver.expect_oneshot_request("/status_200").respond_with_data(
        b"Some data here!",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    httpserver.expect_oneshot_request("/status_404").respond_with_data(
        b"Not Found",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=404,
    )
    httpserver.expect_oneshot_request("/status_504").respond_with_data(
        b"Gateway timeout",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=504,
    )
    return {
        p: httpserver.url_for(p) for p in ["/status_200", "/status_404", "/status_504"]
    }


@run_in_pyodide
async def test_pyfetch_raise_for_status_does_not_raise_200(
    selenium, raise_for_status_fixture
):
    import pytest

    from pyodide.http import HttpStatusError, pyfetch

    resp = await pyfetch(raise_for_status_fixture["/status_200"])
    resp.raise_for_status()
    assert await resp.string() == "Some data here!"

    resp = await pyfetch(raise_for_status_fixture["/status_404"])
    with pytest.raises(
        HttpStatusError, match="404 Client Error: NOT FOUND for url: .*/status_404"
    ) as error_404:
        resp.raise_for_status()

    assert error_404.value.status == 404
    assert error_404.value.status_text == "NOT FOUND"
    assert error_404.value.url.endswith("status_404")

    resp = await pyfetch(raise_for_status_fixture["/status_504"])
    with pytest.raises(
        HttpStatusError,
        match="504 Server Error: GATEWAY TIMEOUT for url: .*/status_504",
    ) as error_504:
        resp.raise_for_status()

    assert error_504.value.status == 504
    assert error_504.value.status_text == "GATEWAY TIMEOUT"
    assert error_504.value.url.endswith("status_504")


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
def test_pyfetch_headers(selenium, httpserver):
    httpserver.expect_oneshot_request("/test_pyfetch_headers").respond_with_data(
        b"HELLO",
        content_type="text/plain",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "max-age=300",
            "Content-Type": "text/plain",
        },
    )
    request_url = httpserver.url_for("/test_pyfetch_headers")

    selenium.run_async(
        f"""
        import pyodide.http
        response = await pyodide.http.pyfetch('{request_url}')
        headers = response.headers
        assert headers["cache-control"] == "max-age=300"
        assert headers["content-type"] == "text/plain"
        """
    )


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
def test_pyfetch_set_valid_credentials_value(selenium, httpserver):
    httpserver.expect_oneshot_request(
        "/test_pyfetch_set_valid_credentials_value"
    ).respond_with_data(
        b"HELLO",
        content_type="text/plain",
        headers={"Access-Control-Allow-Origin": "*"},
    )
    request_url = httpserver.url_for("/test_pyfetch_set_valid_credentials_value")

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
def test_pyfetch_cors_error(selenium, httpserver):
    httpserver.expect_oneshot_request("/test_pyfetch_cors_error").respond_with_data(
        b"HELLO",
        content_type="text/plain",
    )
    request_url = httpserver.url_for("/test_pyfetch_cors_error")

    selenium.run_async(
        f"""
        import pyodide.http
        from unittest import TestCase
        raises = TestCase().assertRaises
        with raises(OSError):
            data = await pyodide.http.pyfetch('{request_url}')
        """
    )


@run_in_pyodide
async def test_pyfetch_manually_abort(selenium):
    import pytest

    from pyodide.http import AbortError, pyfetch

    resp = await pyfetch("/")
    resp.abort("reason")
    with pytest.raises(AbortError, match="reason"):
        await resp.text()


@run_in_pyodide
async def test_pyfetch_abort_on_cancel(selenium):
    from asyncio import CancelledError, ensure_future

    import pytest

    from pyodide.http import pyfetch

    future = ensure_future(pyfetch("/"))
    future.cancel()
    with pytest.raises(CancelledError):
        await future


@run_in_pyodide
async def test_pyfetch_abort_cloned_response(selenium):
    import pytest

    from pyodide.http import AbortError, pyfetch

    resp = await pyfetch("/")
    clone = resp.clone()
    clone.abort()
    with pytest.raises(AbortError):
        await clone.text()


@run_in_pyodide
async def test_pyfetch_custom_abort_signal(selenium):
    import pytest

    from js import AbortController
    from pyodide.http import AbortError, pyfetch

    controller = AbortController.new()
    controller.abort()
    f = pyfetch("/", signal=controller.signal)
    with pytest.raises(AbortError):
        await f
