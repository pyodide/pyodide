import pytest

# FIXME: Cannot use run_in_pyodide here.
#        It seems run_in_pyodide hangs when emscripten throws an unwind exception.


@pytest.mark.driver_timeout(60)
def test_emscripten_loop(selenium_standalone):
    """
    Test that emscripten loop can be run in the background.
    """
    import time

    selenium = selenium_standalone

    selenium.load_package("emscripten-loop-test")
    selenium.run(
        """
        import emscripten_loop_test

        assert emscripten_loop_test.get_counter() == 0

        emscripten_loop_test.main_loop(100, 1)

        raise RuntimeError("Should not reach here!")
        """
    )

    counter1 = selenium.run(
        """
        emscripten_loop_test.get_counter()
        """
    )

    time.sleep(1)

    counter2 = selenium.run(
        """
        emscripten_loop_test.get_counter()
        """
    )

    # main loop should be keep running
    assert counter2 > counter1, (counter1, counter2)


@pytest.mark.driver_timeout(60)
def test_call_stack_restore(selenium_standalone):
    """
    Test that call stack can be restored after emscripten loop.
    """

    selenium = selenium_standalone
    selenium.load_package("emscripten-loop-test")

    selenium.run_js("pyodide.loop.saveThreadState()")

    selenium.run(
        """
        import emscripten_loop_test

        def inner1():
            emscripten_loop_test.main_loop(100, 1)

        def inner2():
            inner1()

        inner2()

        raise RuntimeError("Should not reach here!")
        """
    )

    # Check that the call stack broken
    selenium.run(
        """
        import sys

        frame = sys._getframe()
        func_names = []
        while frame:
            func_names.append(frame.f_code.co_name)
            frame = frame.f_back

        assert inner1 in func_names
        assert inner2 in func_names
        """
    )

    selenium.run_js("pyodide.loop.cancel(); pyodide.loop.restoreThreadState()")

    # Check that the call stack is restored
    selenium.run(
        """
        import sys
        frame = sys._getframe()
        func_names = []
        while frame:
            func_names.append(frame.f_code.co_name)
            frame = frame.f_back

        assert "inner1" not in func_names
        assert "inner2" not in func_names
        """
    )
