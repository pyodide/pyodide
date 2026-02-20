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


@pytest.mark.xfail_browsers(node="XMLHttpRequest is not available in node")
class TestPyxhr:
    """Test suite for pyxhr synchronous HTTP client."""

    def test_xhr_basic_get(self, selenium, xhr_test_server):
        """Test basic GET request with pyxhr."""
        request_url = xhr_test_server.url_for("/xhr/get")

        result_json = selenium.run(f"""
            import json
            from pyodide.http import pyxhr
            response = pyxhr.get('{request_url}')
            result = {{
                'status_code': response.status_code,
                'data': response.json(),
                'ok': response.ok
            }}
            json.dumps(result)
        """)

        import json

        result = json.loads(result_json)
        assert result["status_code"] == 200
        assert result["data"]["message"] == "GET success"
        assert result["ok"] is True

    def test_xhr_post_json(self, selenium, xhr_test_server):
        """Test POST request with JSON data."""
        request_url = xhr_test_server.url_for("/xhr/post")

        result_json = selenium.run(f"""
            import json
            from pyodide.http import pyxhr
            response = pyxhr.post('{request_url}', json={{"test": "data"}})
            result = {{
                'status_code': response.status_code,
                'data': response.json()
            }}
            json.dumps(result)
        """)

        import json

        result = json.loads(result_json)
        assert result["status_code"] == 200
        assert result["data"]["message"] == "POST success"

    def test_xhr_custom_headers(self, selenium, xhr_test_server):
        """Test custom headers in xhr request."""
        request_url = xhr_test_server.url_for("/xhr/headers")

        result = selenium.run(f"""
            from pyodide.http import pyxhr
            response = pyxhr.get('{request_url}', headers={{"X-Test-Header": "test-value"}})
            data = response.json()
            data['headers'].get('X-Test-Header', 'not-found')
        """)

        assert result == "test-value"

    def test_xhr_basic_auth(self, selenium, xhr_test_server):
        """Test basic authentication with pyxhr."""
        request_url = xhr_test_server.url_for("/xhr/auth")

        result_json = selenium.run(f"""
            import json
            from pyodide.http import pyxhr
            response = pyxhr.get('{request_url}', auth=('test', 'pass'))
            result = {{
                'status_code': response.status_code,
                'data': response.json()
            }}
            json.dumps(result)
        """)

        import json

        result = json.loads(result_json)
        assert result["status_code"] == 200
        assert result["data"]["authenticated"] is True

    def test_xhr_url_params(self, selenium, xhr_test_server):
        """Test URL parameters with pyxhr."""
        request_url = xhr_test_server.url_for("/xhr/get")

        result = selenium.run(f"""
            from pyodide.http import pyxhr
            response = pyxhr.get('{request_url}', params={{"key1": "value1", "key2": "value2"}})
            # Check that the response URL contains the parameters
            '?' in response.url and 'key1=value1' in response.url and 'key2=value2' in response.url
        """)

        assert result is True

    def test_xhr_error_status(self, selenium, xhr_test_server):
        """Test error status handling."""
        request_url = xhr_test_server.url_for("/xhr/error")

        result_json = selenium.run(f"""
            import json
            from pyodide.http import pyxhr, HttpStatusError
            response = pyxhr.get('{request_url}')
            try:
                response.raise_for_status()
                result = {{"error_raised": False}}
            except HttpStatusError as e:
                result = {{"error_raised": True, "status": e.status}}
            json.dumps(result)
        """)

        import json

        result = json.loads(result_json)
        assert result["error_raised"] is True
        assert result["status"] == 404

    def test_xhr_response_properties(self, selenium, xhr_test_server):
        """Test XHRResponse properties."""
        request_url = xhr_test_server.url_for("/xhr/get")

        result_json = selenium.run(f"""
            import json
            from pyodide.http import pyxhr
            response = pyxhr.get('{request_url}')
            result = {{
                'status_code': response.status_code,
                'text_type': type(response.text).__name__,
                'content_type': type(response.content).__name__,
                'headers_type': type(response.headers).__name__,
                'ok': response.ok,
                'has_url': bool(response.url)
            }}
            json.dumps(result)
        """)

        import json

        result = json.loads(result_json)
        assert result["status_code"] == 200
        assert result["text_type"] == "str"
        assert result["content_type"] == "bytes"
        assert result["headers_type"] == "dict"
        assert result["ok"] is True
        assert result["has_url"] is True

    def test_xhr_all_methods(self, selenium, xhr_test_server):
        """Test all HTTP methods are available."""

        result_json = selenium.run("""
            import json
            from pyodide.http import pyxhr
            methods = ['get', 'post', 'put', 'delete', 'head', 'patch', 'options']
            available_methods = []
            for method in methods:
                if hasattr(pyxhr, method) and callable(getattr(pyxhr, method)):
                    available_methods.append(method)
            json.dumps(available_methods)
        """)

        import json

        result = json.loads(result_json)
        expected_methods = ["get", "post", "put", "delete", "head", "patch", "options"]
        assert result == expected_methods


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
