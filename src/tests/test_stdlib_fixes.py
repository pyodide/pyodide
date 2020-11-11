import pytest


def test_threading_import(selenium):
    # Importing threading works
    selenium.run(
        """
        from threading import Thread
        """
    )

    selenium.run(
        """
        from threading import RLock

        with RLock():
            pass
        """
    )

    selenium.run(
        """
        from threading import Lock

        with Lock():
            pass
        """
    )

    # Starting a thread doesn't work
    msg = "can't start new thread"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            from threading import Thread

            def set_state():
                return
            th = Thread(target=set_state)
            th.start()
            """
        )


def test_ctypes_import(selenium):
    selenium.run(
        """
        import ctypes
        """
    )
