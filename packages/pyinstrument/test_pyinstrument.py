import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["pyinstrument"])
async def test_pyinstrument(selenium):
    """Check that we can run the profiler on async code

    without errors.
    """
    import asyncio

    from pyinstrument import Profiler

    p = Profiler()
    with p:
        await asyncio.sleep(0.1)

    p.print()
