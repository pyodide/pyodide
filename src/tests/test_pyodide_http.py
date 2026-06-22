import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node


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


@pytest.mark.xfail_browsers(node="Request requires fully qualified url")
@run_in_pyodide
async def test_pyfetch_js_request(selenium):
    from js import Request
    from pyodide.http import pyfetch

    resp = await pyfetch(Request.new("console.html"))
    assert resp.url.endswith("/console.html")
    assert resp.status == 200


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
    httpserver.expect_oneshot_request("/status_900").respond_with_data(
        b"Wrong error code",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=900,
    )
    return {
        p: httpserver.url_for(p)
        for p in ["/status_200", "/status_404", "/status_504", "/status_900"]
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

    resp = await pyfetch(raise_for_status_fixture["/status_900"])

    # this should not raise as it is above 600.
    resp.raise_for_status()

    with pytest.raises(
        HttpStatusError,
        match="900 Invalid error code not between 400 and 599: UNKNOWN for url: a_fake_url",
    ) as error_900:
        # check that even with >600 error code, we get a message that matches
        raise HttpStatusError(900, "UNKNOWN", "a_fake_url")

    assert error_900.value.status == 900
    assert error_900.value.status_text == "UNKNOWN"
    assert error_900.value.url == "a_fake_url"


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

    @run_in_pyodide
    async def inner(selenium, url):
        import http.client

        from pyodide.http import pyfetch

        response = await pyfetch(url)
        headers = response.headers
        assert isinstance(headers, http.client.HTTPMessage)
        assert headers["cache-control"] == "max-age=300"
        assert headers["content-type"] == "text/plain"
        assert headers["Cache-Control"] == "max-age=300"
        assert headers["Content-Type"] == "text/plain"
        assert headers["CONTENT-TYPE"] == "text/plain"
        assert headers.get("content-type") == "text/plain"
        assert headers.get("nonexistent") is None
        assert headers.get("nonexistent", "default") == "default"
        assert "content-type" in headers
        assert "Content-Type" in headers
        assert "nonexistent" not in headers

    inner(selenium, request_url)


def test_pyfetch_headers_duplicate_comma_joined(selenium, httpserver):
    import werkzeug

    def handler(request):
        resp = werkzeug.Response("OK", status=200, content_type="text/plain")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Expose-Headers"] = "X-Tag"
        resp.headers.add("X-Tag", "first")
        resp.headers.add("X-Tag", "second")
        return resp

    httpserver.expect_oneshot_request(
        "/test_pyfetch_headers_duplicate_comma_joined"
    ).respond_with_handler(handler)
    request_url = httpserver.url_for("/test_pyfetch_headers_duplicate_comma_joined")

    @run_in_pyodide
    async def inner(selenium, url):
        from pyodide.http import pyfetch

        response = await pyfetch(url)
        headers = response.headers
        tags = headers.get_all("X-Tag")
        assert tags is not None
        assert len(tags) == 1
        assert tags[0] == "first, second"

    inner(selenium, request_url)


@only_node
def test_pyfetch_headers_duplicate_set_cookie(selenium, httpserver):
    import werkzeug

    def handler(request):
        resp = werkzeug.Response("OK", status=200, content_type="text/plain")
        resp.headers.add("Set-Cookie", "a=1; Path=/")
        resp.headers.add("Set-Cookie", "b=2; Path=/")
        resp.headers.add("Set-Cookie", "c=3; Path=/")
        return resp

    httpserver.expect_oneshot_request(
        "/test_pyfetch_headers_duplicate_set_cookie"
    ).respond_with_handler(handler)
    request_url = httpserver.url_for("/test_pyfetch_headers_duplicate_set_cookie")

    @run_in_pyodide
    async def inner(selenium, url):
        from pyodide.http import pyfetch

        response = await pyfetch(url)
        headers = response.headers
        cookies = headers.get_all("Set-Cookie")
        assert cookies is not None
        assert len(cookies) == 3
        assert "a=1" in cookies[0]
        assert "b=2" in cookies[1]
        assert "c=3" in cookies[2]

    inner(selenium, request_url)


def test_pyfetch_headers_get_all(selenium, httpserver):
    httpserver.expect_oneshot_request(
        "/test_pyfetch_headers_get_all"
    ).respond_with_data(
        b"OK",
        content_type="text/plain",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "X-Custom",
            "X-Custom": "value1",
        },
    )
    request_url = httpserver.url_for("/test_pyfetch_headers_get_all")

    @run_in_pyodide
    async def inner(selenium, url):
        from pyodide.http import pyfetch

        response = await pyfetch(url)
        headers = response.headers

        vals = headers.get_all("X-Custom")
        assert vals is not None
        assert len(vals) == 1
        assert vals[0] == "value1"

        assert headers.get_all("X-Nonexistent") is None

    inner(selenium, request_url)


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
    node="No cors problem in node",
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


@run_in_pyodide
async def test_pyfetch_custom_fetcher(selenium):
    from js import Promise, Response
    from pyodide.http import pyfetch

    call_args = []

    def custom_fetcher(url, options):
        call_args.append((url, options.to_py()))
        return Promise.resolve(Response.new("test"))

    response = await pyfetch(
        "test_url", fetcher=custom_fetcher, headers={"X-Test": "true"}
    )

    assert len(call_args) == 1
    assert call_args[0][0].url.endswith("/test_url")
    assert "headers" in call_args[0][1]
    assert call_args[0][1]["headers"]["X-Test"] == "true"

    assert await response.text() == "test"


@run_in_pyodide
async def test_FetchResponse_empty_string(selenium):
    import js
    from pyodide.http import FetchResponse

    # Test that FetchResponse can handle empty string URLs
    # This should not raise an error
    resp = FetchResponse("", await js.fetch(""))
    assert resp._url == ""
    cloned = resp.clone()
    assert cloned._url == ""


# pyxhr tests
@pytest.fixture
def xhr_test_server(httpserver):
    """Set up test endpoints for xhr testing."""
    import werkzeug

    httpserver.expect_request("/xhr/get").respond_with_data(
        b'{"message": "GET success"}',
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )

    def post_handler(request):
        if request.method == "OPTIONS":
            return werkzeug.Response(
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                },
            )
        return werkzeug.Response(
            '{"message": "POST success"}',
            status=200,
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    httpserver.expect_request("/xhr/post").respond_with_handler(post_handler)

    def headers_handler(request):
        import json

        if request.method == "OPTIONS":
            return werkzeug.Response(
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "X-Test-Header, Content-Type",
                },
            )
        response_data = {"headers": dict(request.headers), "method": request.method}
        return werkzeug.Response(
            json.dumps(response_data),
            status=200,
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    httpserver.expect_request("/xhr/headers").respond_with_handler(headers_handler)

    def auth_handler(request):
        if request.method == "OPTIONS":
            return werkzeug.Response(
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type",
                },
            )
        auth_header = request.headers.get("Authorization", "")
        if auth_header == "Basic dGVzdDpwYXNz":  # base64('test:pass')
            return werkzeug.Response(
                '{"authenticated": true}',
                status=200,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
        else:
            return werkzeug.Response(
                '{"error": "unauthorized"}',
                status=401,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )

    httpserver.expect_request("/xhr/auth").respond_with_handler(auth_handler)

    httpserver.expect_request("/xhr/error").respond_with_data(
        b'{"error": "Not Found"}',
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
        status=404,
    )

    return httpserver


@pytest.fixture
def xhr_urls(xhr_test_server):
    return {
        path: xhr_test_server.url_for(f"/xhr/{path}")
        for path in ["get", "post", "headers", "auth", "error"]
    }


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
class TestPyxhr:

    def test_xhr_basic_get(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.get(url)
            assert response.status_code == 200
            assert response.json()["message"] == "GET success"
            assert response.ok is True

        inner(selenium, xhr_urls["get"])

    def test_xhr_post_json(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.post(url, json={"test": "data"})
            assert response.status_code == 200
            assert response.json()["message"] == "POST success"

        inner(selenium, xhr_urls["post"])

    def test_xhr_custom_headers(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.get(url, headers={"X-Test-Header": "test-value"})
            data = response.json()
            assert data["headers"].get("X-Test-Header", "not-found") == "test-value"

        inner(selenium, xhr_urls["headers"])

    def test_xhr_basic_auth(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.get(url, auth=("test", "pass"))
            assert response.status_code == 200
            assert response.json()["authenticated"] is True

        inner(selenium, xhr_urls["auth"])

    def test_xhr_url_params(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.get(url, params={"key1": "value1", "key2": "value2"})
            assert "?" in response.url
            assert "key1=value1" in response.url
            assert "key2=value2" in response.url

        inner(selenium, xhr_urls["get"])

    def test_xhr_error_status(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            import pytest

            from pyodide.http import HttpStatusError, pyxhr

            response = pyxhr.get(url)
            with pytest.raises(HttpStatusError) as exc_info:
                response.raise_for_status()
            assert exc_info.value.status == 404

        inner(selenium, xhr_urls["error"])

    def test_xhr_response_properties(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            import http.client

            from pyodide.http import pyxhr

            response = pyxhr.get(url)
            assert response.status_code == 200
            assert isinstance(response.text, str)
            assert isinstance(response.content, bytes)
            assert isinstance(response.headers, http.client.HTTPMessage)
            assert response.headers["Content-Type"] == response.headers["content-type"]
            assert response.ok is True
            assert bool(response.url)

        inner(selenium, xhr_urls["get"])

    def test_xhr_headers_case_insensitive(self, selenium, xhr_urls):
        @run_in_pyodide
        def inner(selenium, url):
            import http.client

            from pyodide.http import pyxhr

            response = pyxhr.get(url)
            headers = response.headers

            assert isinstance(headers, http.client.HTTPMessage)
            assert headers["content-type"] == headers["Content-Type"] == headers["CONTENT-TYPE"]
            assert headers.get("content-type") is not None
            assert "content-type" in headers
            assert "Content-Type" in headers
            assert headers.get_all("content-type") is not None

        inner(selenium, xhr_urls["get"])

    def test_xhr_headers_duplicate(self, selenium, httpserver):
        import werkzeug

        def handler(request):
            if request.method == "OPTIONS":
                return werkzeug.Response(
                    status=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, OPTIONS",
                        "Access-Control-Expose-Headers": "X-Tag",
                    },
                )
            resp = werkzeug.Response("OK", status=200, content_type="text/plain")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Expose-Headers"] = "X-Tag"
            resp.headers.add("X-Tag", "first")
            resp.headers.add("X-Tag", "second")
            return resp

        httpserver.expect_request("/xhr/duplicate_headers").respond_with_handler(
            handler
        )
        url = httpserver.url_for("/xhr/duplicate_headers")

        @run_in_pyodide
        def inner(selenium, url):
            from pyodide.http import pyxhr

            response = pyxhr.get(url)
            headers = response.headers
            tags = headers.get_all("x-tag")
            assert tags is not None
            assert "first" in tags[0]
            assert "second" in tags[-1]

        inner(selenium, url)

    def test_xhr_all_methods(self, selenium):
        @run_in_pyodide
        def inner(selenium):
            from pyodide.http import pyxhr

            methods = ["get", "post", "put", "delete", "head", "patch", "options"]
            for method in methods:
                assert hasattr(pyxhr, method)
                assert callable(getattr(pyxhr, method))

        inner(selenium)


def test_xhr_not_in_browser(monkeypatch):
    """Test that _xhr_request raises RuntimeError when not in a browser environment."""
    import pytest

    # Mock the IN_PYODIDE flag to simulate non-browser environment
    import pyodide.http

    monkeypatch.setattr(pyodide.http, "IN_PYODIDE", False)

    # Test that _xhr_request raises RuntimeError when called outside browser
    with pytest.raises(
        RuntimeError, match="XMLHttpRequest is only available in browser environments"
    ):
        from pyodide.http import pyxhr

        # This should raise RuntimeError when trying to make a request
        pyxhr.get("http://test.com")
