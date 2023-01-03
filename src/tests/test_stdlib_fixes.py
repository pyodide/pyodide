import pytest
from pytest_pyodide import run_in_pyodide


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


@run_in_pyodide
def test_multiprocessing(selenium):
    import multiprocessing  # noqa: F401
    from multiprocessing import connection, cpu_count  # noqa: F401

    import pytest

    res = cpu_count()
    assert isinstance(res, int)
    assert res > 0

    from multiprocessing import Process

    def func():
        return

    process = Process(target=func)
    with pytest.raises(OSError, match="Function not implemented"):
        process.start()


@run_in_pyodide
def test_ctypes_util_find_library(selenium):
    import os
    from ctypes.util import find_library
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "libfoo.so"), "wb") as f:
            f.write(b"\x00asm\x01\x00\x00\x00\x00\x08\x04name\x02\x01\x00")
        with open(os.path.join(tmpdir, "libbar.so"), "wb") as f:
            f.write(b"\x00asm\x01\x00\x00\x00\x00\x08\x04name\x02\x01\x00")

        os.environ["LD_LIBRARY_PATH"] = tmpdir

        assert find_library("foo") == os.path.join(tmpdir, "libfoo.so")
        assert find_library("bar") == os.path.join(tmpdir, "libbar.so")
        assert find_library("baz") is None
