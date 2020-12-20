import pytest
from selenium.common.exceptions import WebDriverException


def test_interrupt_context_manager(selenium):
    selenium.run(
        """
        x = 0
        def temp():
            global x
            if x < 10000:
                return 0
            return 2
        import pyodide
        """
    )
    msg = "KeyboardInterrupt"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            with pyodide.interrupt_buffer(temp):
                while True: x += 1
            """
        )
    selenium.run(
        """
        x = 0
        while x < 20000: x += 1
        """
    )


def test_interrupt(selenium):
    selenium.run(
        """
        x = 0
        y = 0
        def temp():
            global x
            if x < 10000:
                return 0
            global y
            y = x
            x = 0
            return 2
        import pyodide
        pyodide.set_interrupt_buffer(temp)
        """
    )
    msg = "KeyboardInterrupt"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            while True: x += 1
            """
        )
    assert selenium.run("y") > 10000


def test_interrupt_bad_return_type(selenium):
    msg = "TypeError: an integer is required"
    with pytest.raises(WebDriverException, match=msg):
        result = selenium.run(
            """
            def temp():
                return [True]
            import pyodide
            pyodide.set_interrupt_buffer(temp)
            x = 0
            while x < 20000: x += 1
            """
        )
    result = selenium.run(
        """
        pyodide.get_interrupt_buffer() is None
        """
    )
    assert result is True


def test_interrupt_throws(selenium):
    msg = "Exception: hi"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            def temp():
                raise Exception("hi")
                return True
            import pyodide
            pyodide.set_interrupt_buffer(temp)
            x = 0
            while x < 20000: x += 1        
            """
        )

    result = selenium.run(
        """
        pyodide.get_interrupt_buffer() is None
        """
    )
    assert result is True


def test_interrupt_trace(selenium):
    selenium.run(
        """
        x = 0
        def temp():
            global x
            if x < 10000:
                return 0
            return 2
        import pyodide
        y = 0
        def dummy():
            pass
        def trace(a, b, c):
            global y
            y += 1
            return trace
        import sys
        """
    )
    msg = "KeyboardInterrupt"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            with pyodide.interrupt_buffer(temp):
                sys.settrace(trace)
                assert sys.gettrace() == trace
                while True: dummy() ; x += 1
            """
        )
    assert selenium.run("y") > 10000
