import pytest

# FIXME: separate webworker tests to avoid multiple safari instance being created.
#        pytest-pyodide should be able to handle this but it doesn't work as expected.
#        (https://github.com/pyodide/pytest-pyodide/blob/f957dcd510eb62af286df608ed9a1861adce1b6d/pytest_pyodide/hook.py#L274)


def test_webworker_zero_timeout1(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        import asyncio
        await asyncio.sleep(0)
        42
        """
    )
    assert output == 42


@pytest.mark.xfail_browsers(safari="Safari uses setTimeout as a fallback for 0ms delay")
def test_webworker_zero_timeout2(selenium_webworker_standalone, script_type):
    selenium = selenium_webworker_standalone
    output = selenium.run_webworker(
        """
        import asyncio
        import time

        from pyodide_js._api import detectEnvironment

        assert detectEnvironment().to_py().get("IN_BROWSER_WEB_WORKER") is True

        now = time.time()

        for _ in range(1000):
            await asyncio.sleep(0)

        done = time.time()
        elapsed = done - now

        # Very rough check, we hope it's less than 4s (1000 * 4ms [setTimeout delay in most browsers])
        assert elapsed < 4, f"elapsed: {elapsed}s"

        42
        """
    )

    assert output == 42
