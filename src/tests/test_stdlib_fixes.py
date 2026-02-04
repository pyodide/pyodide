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
    with pytest.raises(ModuleNotFoundError, match="No module named '_multiprocessing'"):
        process.start()


@pytest.mark.requires_dynamic_linking
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


@run_in_pyodide
def test_zipimport_traceback(selenium):
    """
    Test that traceback of modules loaded from zip file are shown as intended.

    For .py files, the traceback should show the path to the .py file in the
    zip file, e.g. "/lib/python311.zip/path/to/module.py".

    For .pyc files (TODO), the traceback only shows filename, e.g. "module.py".
    """
    import json.decoder
    import pathlib
    import sys
    import traceback

    zipfile = f"python{sys.version_info[0]}{sys.version_info[1]}.zip"

    try:
        pathlib.Path("not/exists").write_text("hello")
    except Exception:
        _, _, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)

        assert zipfile in tb[-1].filename.split("/")
        assert tb[-1].filename == pathlib.__file__  # type:ignore[attr-defined]

    try:
        json.decoder.JSONDecoder().decode(1)  # type: ignore[arg-type]
    except Exception:
        _, _, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)

        assert zipfile in tb[-1].filename.split("/")
        assert tb[-1].filename == json.decoder.__file__


@run_in_pyodide
def test_zipimport_check_non_stdlib(selenium):
    """
    Check if unwanted modules are included in the zip file.
    """
    import pathlib
    import shutil
    import sys
    import tempfile

    extra_files = {
        "LICENSE.txt",
        "__phello__",
        "__hello__",
        "_sysconfigdata__emscripten_wasm32-emscripten",
        "site-packages",
        "lib-dynload",
        "pyodide",
        "_pyodide",
    }

    stdlib_names = sys.stdlib_module_names | extra_files

    zipfile = pathlib.Path(shutil.__file__).parent
    tmpdir = pathlib.Path(tempfile.mkdtemp())

    shutil.unpack_archive(zipfile, tmpdir, "zip")
    for f in tmpdir.glob("*"):
        assert f.name.removesuffix(".py") in stdlib_names, f.name
