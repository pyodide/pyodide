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

    selenium.run(
        """
        import threading
        threading.local(); pass
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


def test_multiprocessing(selenium):
    selenium.run("import multiprocessing")

    res = selenium.run(
        """
        from multiprocessing import cpu_count
        cpu_count()
        """
    )
    assert isinstance(res, int)
    assert res > 0

    msg = "Function not implemented"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            from multiprocessing import Process

            def func():
                return
            process = Process(target=func)
            process.start()
            """
        )
