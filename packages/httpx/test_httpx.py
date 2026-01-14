import pytest
from pytest_pyodide import run_in_pyodide
from pytest_httpserver import RequestMatcher
from conftest import requires_jspi
import time


def sleeping(request):
    time.sleep(0.5)


@pytest.fixture
def urls_fixture(httpserver):
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
    httpserver.expect_request("/timeout").respond_with_handler(sleeping)

    return {
        p: httpserver.url_for(p)
        for p in ["/status_200", "/status_404", "/status_504", "/timeout"]
    }


@requires_jspi
@run_in_pyodide(packages=["httpx"])
def test_get_sync(selenium, urls_fixture):
    import httpx
    import pytest

    response = httpx.get(urls_fixture["/status_200"])
    assert response.status_code == 200
    assert response.reason_phrase == "OK"
    assert response.text == "Some data here!"

    resp = httpx.get(urls_fixture["/status_404"])
    with pytest.raises(
        httpx.HTTPStatusError,
        match="Client error '404 Not Found' for url 'http://localhost:[0-9]*/status_404'",
    ):
        resp.raise_for_status()
    resp = httpx.get(urls_fixture["/status_504"])
    with pytest.raises(
        httpx.HTTPStatusError,
        match="Server error '504 Gateway Timeout' for url 'http://localhost:[0-9]*/status_504'",
    ):
        resp.raise_for_status()


@run_in_pyodide(packages=["httpx"])
async def test_get_async(selenium, urls_fixture):
    import httpx
    import pytest

    async with httpx.AsyncClient() as client:
        resp = await client.get(urls_fixture["/status_200"])
        resp.raise_for_status()
        assert resp.text == "Some data here!"

        resp = await client.get(urls_fixture["/status_404"])
        with pytest.raises(
            httpx.HTTPStatusError,
            match="Client error '404 Not Found' for url 'http://localhost:[0-9]*/status_404'",
        ):
            resp.raise_for_status()

        resp = await client.get(urls_fixture["/status_504"])
        with pytest.raises(
            httpx.HTTPStatusError,
            match="Server error '504 Gateway Timeout' for url 'http://localhost:[0-9]*/status_504'",
        ):
            resp.raise_for_status()


@requires_jspi
@run_in_pyodide(packages=["httpx"])
def test_get_sync_timeout(selenium, urls_fixture):
    import httpx
    import pytest

    with pytest.raises(httpx.TimeoutException):
        response = httpx.get(urls_fixture["/timeout"], timeout=0.1)


@run_in_pyodide(packages=["httpx"])
async def test_get_async_timeout(selenium, urls_fixture):
    import httpx
    import pytest

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.TimeoutException):
            await client.get(urls_fixture["/timeout"], timeout=0.1)


@run_in_pyodide(packages=["httpx"])
async def test_header_decoding(selenium):
    import httpx

    # Need to make a real request to catch this.
    httpx.get("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs"
        )


class MyMatcher(RequestMatcher):
    def match(self, request) -> bool:
        match = super().match(request)
        if not match:  # existing parameters didn't match -> return with False
            return match

        # match the json's "value" key: if it is an integer and it is an even
        # number, it returns True
        json = request.json
        if isinstance(json, dict):
            return json.get("text", None) == "Hello, world!"

        return False


@pytest.fixture
def post_json_url(httpserver):
    httpserver.expect(MyMatcher("/status_200")).respond_with_data(
        b"Some data here!",
        content_type="text/text",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    return httpserver.url_for("/status_200")


@requires_jspi
@pytest.mark.xfail(reason="Passes locally, fails in CI")
@run_in_pyodide(packages=["httpx"])
def test_sync_post_json(selenium, post_json_url) -> None:
    import httpx

    response = httpx.post(post_json_url, json={"text": "Hello, world!"})
    assert response.status_code == 200


@pytest.mark.xfail(reason="Passes locally, fails in CI")
@run_in_pyodide(packages=["httpx"])
async def test_async_post_json(selenium, post_json_url) -> None:
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(post_json_url, json={"text": "Hello, world!"})
        assert response.status_code == 200
