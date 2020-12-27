def test_numpy(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    selenium.run("x = numpy.ones((32, 64))")
    assert selenium.run_js("return pyodide.pyimport('x').length == 32")
    for i in range(32):
        assert selenium.run_js(f"return pyodide.pyimport('x')[{i}].length == 64")
        for j in range(64):
            assert selenium.run_js(f"return pyodide.pyimport('x')[{i}][{j}] == 1")


def test_typed_arrays(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    for (jstype, npytype) in (
        ("Int8Array", "int8"),
        ("Uint8Array", "uint8"),
        ("Uint8ClampedArray", "uint8"),
        ("Int16Array", "int16"),
        ("Uint16Array", "uint16"),
        ("Int32Array", "int32"),
        ("Uint32Array", "uint32"),
        ("Float32Array", "float32"),
        ("Float64Array", "float64"),
    ):
        print(jstype, npytype)
        selenium.run_js(f"window.array = new {jstype}([1, 2, 3, 4]);\n")
        assert selenium.run(
            "from js import array\n"
            "npyarray = numpy.asarray(array)\n"
            f'npyarray.dtype.name == "{npytype}" '
            "and npyarray == [1, 2, 3, 4]"
        )


def test_python2js_numpy_dtype(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("numpy")
    selenium.run("import numpy as np")

    expected_result = [[[0, 1], [2, 3]], [[4, 5], [6, 7]]]

    def assert_equal():
        # We have to do this an element at a time, since the Selenium driver
        # for Firefox does not convert TypedArrays to Python correctly
        for i in range(2):
            for j in range(2):
                for k in range(2):
                    assert (
                        selenium.run_js(f"return pyodide.pyimport('x')[{i}][{j}][{k}]")
                        == expected_result[i][j][k]
                    )

    for order in ("C", "F"):
        for dtype in (
            "int8",
            "uint8",
            "int16",
            "uint16",
            "int32",
            "uint32",
            "int64",
            "uint64",
            "float32",
            "float64",
        ):
            selenium.run(
                f"""
                x = np.arange(8, dtype=np.{dtype})
                x = x.reshape((2, 2, 2))
                x = x.copy({order!r})
                """
            )
            assert_equal()
            classname = selenium.run_js(
                "return pyodide.pyimport('x')[0][0].constructor.name"
            )
            if order == "C" and dtype not in ("uint64", "int64"):
                # Here we expect a TypedArray subclass, such as Uint8Array, but
                # not a plain-old Array
                assert classname.endswith("Array")
                assert classname != "Array"
            else:
                assert classname == "Array"
            selenium.run(
                """
                x = x.byteswap().newbyteorder()
                """
            )
            assert_equal()
            classname = selenium.run_js(
                "return pyodide.pyimport('x')[0][0].constructor.name"
            )
            if order == "C" and dtype in ("int8", "uint8"):
                # Here we expect a TypedArray subclass, such as Uint8Array, but
                # not a plain-old Array -- but only for single byte types where
                # endianness doesn't matter
                assert classname.endswith("Array")
                assert classname != "Array"
            else:
                assert classname == "Array"

    assert selenium.run("np.array([True, False])") == [True, False]

    selenium.run("x = np.array([['string1', 'string2'], ['string3', 'string4']])")
    assert selenium.run_js("return pyodide.pyimport('x').length") == 2
    assert selenium.run_js("return pyodide.pyimport('x')[0][0]") == "string1"
    assert selenium.run_js("return pyodide.pyimport('x')[1][1]") == "string4"


def test_python2js_numpy_scalar(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("numpy")
    selenium.run("import numpy as np")

    for dtype in (
        "int8",
        "uint8",
        "int16",
        "uint16",
        "int32",
        "uint32",
        "int64",
        "uint64",
        "float32",
        "float64",
    ):
        selenium.run(
            f"""
            x = np.{dtype}(1)
            """
        )
        assert (
            selenium.run_js(
                """
            return pyodide.pyimport('x') == 1
            """
            )
            is True
        )
        selenium.run(
            """
            x = x.byteswap().newbyteorder()
            """
        )
        assert (
            selenium.run_js(
                """
            return pyodide.pyimport('x') == 1
            """
            )
            is True
        )


def test_runpythonasync_numpy(selenium_standalone):
    selenium_standalone.run_async(
        """
        import numpy as np
        x = np.zeros(5)
        """
    )
    for i in range(5):
        assert selenium_standalone.run_js(f"return pyodide.pyimport('x')[{i}] == 0")


def test_runwebworker_numpy(selenium_standalone):
    output = selenium_standalone.run_webworker(
        """
        import numpy as np
        x = np.zeros(5)
        str(x)
        """
    )
    assert output == "[0. 0. 0. 0. 0.]"
