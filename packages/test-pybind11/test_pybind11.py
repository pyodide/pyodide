import pytest
from pytest_pyodide import run_in_pyodide

from conftest import requires_jspi


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-pybind11"])
def test_pybind11_callback_sync(selenium):
    import pybind11_test

    seen = []
    s = pybind11_test.Solver()
    assert not s.hasCallback()
    s.setCallback(lambda i, msg, data: seen.append((i, msg, data)), "DATA")
    assert s.hasCallback()
    assert s.run(3) == 3
    assert seen == [
        (0, "iteration 0", "DATA"),
        (1, "iteration 1", "DATA"),
        (2, "iteration 2", "DATA"),
    ]
    s.setCallback(None, None)
    assert not s.hasCallback()
    assert s.run(3) == 0

    assert pybind11_test.round_trip_gil(lambda: 7) == 7
    assert pybind11_test.call_with_gil_released(lambda: "ok") == "ok"


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_pybind11_callback_in_promising_task(selenium):
    """pybind11's gil_scoped_acquire works inside a stack switching task.

    Regression test for https://github.com/pyodide/pyodide/issues/6479. The
    module is imported with sync runPython so pybind11 caches the thread state
    that is current there, then the callback is registered and used from
    runPythonAsync, which runs as a promising task.
    """
    result = selenium.run_js(
        """
        await pyodide.loadPackage("test-pybind11");
        pyodide.runPython("import pybind11_test");
        const res = await pyodide.runPythonAsync(`
            import asyncio
            from pyodide.ffi import run_sync

            seen = []
            s = pybind11_test.Solver()
            s.setCallback(lambda i, msg, data: seen.append((i, data)), "D")
            await asyncio.sleep(0)
            fired = s.run(2)
            await asyncio.sleep(0)
            # Stack switch from inside a callback that pybind11 invoked with
            # the GIL released and reacquired.
            s.setCallback(lambda i, msg, data: run_sync(asyncio.sleep(0)), None)
            fired += s.run(2)
            # Stack switch from a Python callable called by C++ with the GIL
            # released around the call.
            async def f():
                await asyncio.sleep(0)
                return "switched"
            r = pybind11_test.call_with_gil_released(lambda: run_sync(f()))
            s.setCallback(None, None)
            [fired, seen, r, pybind11_test.round_trip_gil(lambda: 1)]
        `);
        const out = res.toJs();
        res.destroy();
        return out;
        """
    )
    assert result[0] == 4
    assert result[1] == [[0, "D"], [1, "D"]]
    assert result[2] == "switched"
    assert result[3] == 1
    # And back in sync code afterwards
    assert (
        selenium.run_js(
            """
        return pyodide.runPython(`
            s = pybind11_test.Solver()
            s.setCallback(lambda *a: None, None)
            s.run(2)
        `);
        """
        )
        == 2
    )
