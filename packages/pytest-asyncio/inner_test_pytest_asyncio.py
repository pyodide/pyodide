# mypy: disable-error-code="no-untyped-def"

"""Taken from test_simple.py in pytest-asyncio"""

import asyncio
from textwrap import dedent

import pytest
from pytest import Pytester

pytest_plugins = "pytester"


async def async_coro():
    await asyncio.sleep(0)
    return "ok"


def test_event_loop_fixture(event_loop):
    """Test the injection of the event_loop fixture."""
    assert event_loop
    ret = event_loop.run_until_complete(async_coro())
    assert ret == "ok"


@pytest.mark.asyncio
async def test_asyncio_marker():
    """Test the asyncio pytest marker."""
    await asyncio.sleep(0)


def test_asyncio_marker_compatibility_with_xfail(pytester: Pytester):
    pytester.makepyfile(
        dedent(
            """\
                import pytest

                pytest_plugins = "pytest_asyncio"


                @pytest.mark.xfail(reason="need a failure", strict=True)
                @pytest.mark.asyncio
                async def test_asyncio_marker_fail():
                    raise AssertionError
            """
        )
    )
    result = pytester.runpytest("--asyncio-mode=strict")
    result.assert_outcomes(xfailed=1)


@pytest.mark.asyncio
async def test_asyncio_marker_with_default_param(a_param=None):
    """Test the asyncio pytest marker."""
    await asyncio.sleep(0)
