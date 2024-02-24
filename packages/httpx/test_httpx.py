import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture
def httpx_patch():
    from pathlib import Path

    return (Path(__file__).parent / "httpx_patch.py").read_text()


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
    return {
        p: httpserver.url_for(p) for p in ["/status_200", "/status_404", "/status_504"]
    }


@run_in_pyodide(packages=["httpx"])
async def test_httpx(selenium, urls_fixture, httpx_patch):
    from pathlib import Path

    Path("httpx_patch.py").write_text(httpx_patch)
    import httpx
    import httpx_patch
    import pytest

    async with httpx.AsyncClient() as client:
        resp = await client.get(urls_fixture["/status_200"])
        resp.raise_for_status()
        assert resp.text == "Some data here!"

        resp = await client.get(urls_fixture["/status_404"])
        with pytest.raises(
            Exception, match="404 Client Error: NOT FOUND for url: .*/status_404"
        ):
            resp.raise_for_status()

        resp = await client.get(urls_fixture["/status_504"])
        with pytest.raises(
            Exception, match="504 Server Error: GATEWAY TIMEOUT for url: .*/status_504"
        ):
            resp.raise_for_status()
