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


@run_in_pyodide
def test_encodings_deepfrozen(selenium):
    # We deepfreeze encodings module partially,
    # then after bootstrap, we disable loading frozen modules.

    import codecs
    import encodings
    import encodings.aliases
    import encodings.ascii
    import encodings.cp437
    import encodings.utf_8

    modules = [
        encodings,
        encodings.utf_8,
        encodings.aliases,
        encodings.cp437,
        encodings.ascii,
    ]

    for mod in modules:
        assert "frozen" not in repr(mod)

    all_encodings = [
        "ascii",
        "base64_codec",
        "big5",
        "big5hkscs",
        "bz2_codec",
        "charmap",
        "cp037",
        "cp1006",
        "cp1026",
        "cp1125",
        "cp1140",
        "cp1250",
        "cp1251",
        "cp1252",
        "cp1253",
        "cp1254",
        "cp1255",
        "cp1256",
        "cp1257",
        "cp1258",
        "cp273",
        "cp424",
        "cp437",
        "cp500",
        "cp720",
        "cp737",
        "cp775",
        "cp850",
        "cp852",
        "cp855",
        "cp856",
        "cp857",
        "cp858",
        "cp860",
        "cp861",
        "cp862",
        "cp863",
        "cp864",
        "cp865",
        "cp866",
        "cp869",
        "cp874",
        "cp875",
        "cp932",
        "cp949",
        "cp950",
        "euc_jis_2004",
        "euc_jisx0213",
        "euc_jp",
        "euc_kr",
        "gb18030",
        "gb2312",
        "gbk",
        "hex_codec",
        "hp_roman8",
        "hz",
        "idna",
        "iso2022_jp",
        "iso2022_jp_1",
        "iso2022_jp_2",
        "iso2022_jp_2004",
        "iso2022_jp_3",
        "iso2022_jp_ext",
        "iso2022_kr",
        "iso8859_1",
        "iso8859_10",
        "iso8859_11",
        "iso8859_13",
        "iso8859_14",
        "iso8859_15",
        "iso8859_16",
        "iso8859_2",
        "iso8859_3",
        "iso8859_4",
        "iso8859_5",
        "iso8859_6",
        "iso8859_7",
        "iso8859_8",
        "iso8859_9",
        "johab",
        "koi8_r",
        "koi8_t",
        "koi8_u",
        "kz1048",
        "latin_1",
        "mac_arabic",
        "mac_croatian",
        "mac_cyrillic",
        "mac_farsi",
        "mac_greek",
        "mac_iceland",
        "mac_latin2",
        "mac_roman",
        "mac_romanian",
        "mac_turkish",
        "palmos",
        "ptcp154",
        "punycode",
        "quopri_codec",
        "raw_unicode_escape",
        "rot_13",
        "shift_jis",
        "shift_jis_2004",
        "shift_jisx0213",
        "tis_620",
        "undefined",
        "unicode_escape",
        "utf_16",
        "utf_16_be",
        "utf_16_le",
        "utf_32",
        "utf_32_be",
        "utf_32_le",
        "utf_7",
        "utf_8",
        "utf_8_sig",
        "uu_codec",
        "zlib_codec",
    ]

    for enc in all_encodings:
        codecs.getencoder(enc)
        codecs.getdecoder(enc)
