from pathlib import Path

import pytest


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_different_package_name(
    selenium_webworker_standalone, script_type
):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        import micropip
        micropip.__version__
        """
    )
    assert isinstance(output, str)


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_no_imports(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        42
        """
    )
    assert output == 42


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_missing_import(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    msg = "ModuleNotFoundError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import foo
            """
        )


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_exception(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            42 / 0
            """
        )


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_exception_after_import(
    selenium_webworker_standalone, script_type
):
    selenium = selenium_webworker_standalone
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_webworker(
            """
            import micropip
            42 / 0
            """
        )


@pytest.mark.xfail_browsers(chrome="flaky")
def test_runwebworker_micropip(selenium_webworker_standalone, httpserver, script_type):
    selenium = selenium_webworker_standalone

    test_file_name = "dummy_pkg-0.1.0-py3-none-any.whl"
    test_file_path = Path(__file__).parent / "wheels" / test_file_name
    test_file_data = test_file_path.read_bytes()

    httpserver.expect_oneshot_request("/" + test_file_name).respond_with_data(
        test_file_data,
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    request_url = httpserver.url_for("/" + test_file_name)

    output = selenium.run_webworker(
        f"""
        import micropip
        await micropip.install({request_url!r})
        import dummy_pkg

        print(dummy_pkg.__name__)
        """
    )
    assert output == "dummy_pkg"
