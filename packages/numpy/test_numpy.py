import pytest


def test_numpy(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    selenium.run("x = numpy.ones((32, 64))")
    assert selenium.run_js("return pyodide.globals.get('x').toJs().length == 32")
    for i in range(32):
        assert selenium.run_js(
            f"return pyodide.globals.get('x').toJs()[{i}].length == 64"
        )
        for j in range(64):
            assert selenium.run_js(
                f"return pyodide.globals.get('x').toJs()[{i}][{j}] == 1"
            )


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
            "npyarray = numpy.asarray(array.to_py())\n"
            f'npyarray.dtype.name == "{npytype}" '
            "and npyarray == [1, 2, 3, 4]"
        )


@pytest.mark.parametrize("order", ("C", "F"))
@pytest.mark.parametrize(
    "dtype",
    (
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
    ),
)
def test_python2js_numpy_dtype(selenium, order, dtype):

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
                        selenium.run_js(
                            f"return Number(pyodide.globals.get('x').toJs()[{i}][{j}][{k}])"
                        )
                        == expected_result[i][j][k]
                    )

    selenium.run(
        f"""
        x = np.arange(8, dtype=np.{dtype})
        x = x.reshape((2, 2, 2))
        x = x.copy({order!r})
        """
    )
    assert_equal()
    classname = selenium.run_js(
        "return pyodide.globals.get('x').toJs()[0][0].constructor.name"
    )
    # We expect a TypedArray subclass, such as Uint8Array, but not a plain-old
    # Array
    assert classname.endswith("Array")
    assert classname != "Array"
    selenium.run(
        """
        x = x.byteswap().newbyteorder()
        """
    )
    assert_equal()
    classname = selenium.run_js(
        "return pyodide.globals.get('x').toJs()[0][0].constructor.name"
    )
    assert classname.endswith("Array")
    assert classname != "Array"

    assert selenium.run("np.array([True, False])") == [True, False]


def test_py2js_buffer_clear_error_flag(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy as np")
    selenium.run("x = np.array([['string1', 'string2'], ['string3', 'string4']])")
    selenium.run_js(
        """
        pyodide.globals.get("x")
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )


@pytest.mark.parametrize(
    "dtype",
    (
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
    ),
)
def test_python2js_numpy_scalar(selenium, dtype):

    selenium.load_package("numpy")
    selenium.run("import numpy as np")
    selenium.run(
        f"""
        x = np.{dtype}(1)
        """
    )
    assert (
        selenium.run_js(
            """
        return pyodide.globals.get('x') == 1
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
        return pyodide.globals.get('x') == 1
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
        assert selenium_standalone.run_js(
            f"return pyodide.globals.get('x').toJs()[{i}] == 0"
        )


@pytest.mark.driver_timeout(30)
def test_runwebworker_numpy(selenium_webworker_standalone):
    if selenium_webworker_standalone.browser == "firefox":
        pytest.xfail("Timeout in WebWorker when using numpy in Firefox 87")

    output = selenium_webworker_standalone.run_webworker(
        """
        import numpy as np
        x = np.zeros(5)
        str(x)
        """
    )
    assert output == "[0. 0. 0. 0. 0.]"


def test_get_buffer(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import numpy as np
            x = np.arange(24)
            z1 = x.reshape([8,3])
            z2 = z1[-1::-1]
            z3 = z1[::,-1::-1]
            z4 = z1[-1::-1,-1::-1]
        `);
        for(let x of ["z1", "z2", "z3", "z4"]){
            let z = pyodide.pyimport(x).getBuffer("u32");
            for(let idx1 = 0; idx1 < 8; idx1++) {
                for(let idx2 = 0; idx2 < 3; idx2++){
                    let v1 = z.data[z.offset + z.strides[0] * idx1 + z.strides[1] * idx2];
                    let v2 = pyodide.runPython(`repr(${x}[${idx1}, ${idx2}])`);
                    console.log(`${v1}, ${typeof(v1)}, ${v2}, ${typeof(v2)}, ${v1===v2}`);
                    if(v1.toString() !== v2){
                        throw new Error(`Discrepancy ${x}[${idx1}, ${idx2}]: ${v1} != ${v2}`);
                    }
                }
            }
            z.release();
        }
        """
    )


@pytest.mark.parametrize(
    "arg",
    [
        "np.arange(6).reshape((2, -1))",
        "np.arange(12).reshape((3, -1))[::2, ::2]",
        "np.arange(12).reshape((3, -1))[::-1, ::-1]",
        "np.arange(12).reshape((3, -1))[::, ::-1]",
        "np.arange(12).reshape((3, -1))[::-1, ::]",
        "np.arange(12).reshape((3, -1))[::-2, ::-2]",
        "np.arange(6).reshape((2, -1)).astype(np.int8, order='C')",
        "np.arange(6).reshape((2, -1)).astype(np.int8, order='F')",
        "np.arange(6).reshape((2, -1, 1))",
        "np.ones((1, 1))[0:0]",  # shape[0] == 0
        "np.ones(1)",  # ndim == 0
    ]
    + [
        f"np.arange(3).astype(np.{type_})"
        for type_ in ["int8", "uint8", "int16", "int32", "float32", "float64"]
    ],
)
def test_get_buffer_roundtrip(selenium, arg):
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            import numpy as np
            x = {arg}
        `);
        window.x_js_buf = pyodide.pyimport("x").getBuffer();
        x_js_buf.length = x_js_buf.data.length;
        """
    )

    selenium.run_js(
        """
        pyodide.runPython(`
            import itertools
            from unittest import TestCase
            from js import x_js_buf
            assert_equal = TestCase().assertEqual

            assert_equal(x_js_buf.ndim, x.ndim)
            assert_equal(x_js_buf.shape.to_py(), list(x.shape))
            assert_equal(x_js_buf.strides.to_py(), [s/x.itemsize for s in x.data.strides])
            assert_equal(x_js_buf.format, x.data.format)
            if len(x) == 0:
                assert x_js_buf.length == 0
            else:
                minoffset = 1000
                maxoffset = 0
                for tup in itertools.product(*[range(n) for n in x.shape]):
                    offset = x_js_buf.offset + sum(x*y for (x,y) in zip(tup, x_js_buf.strides))
                    minoffset = min(offset, minoffset)
                    maxoffset = max(offset, maxoffset)
                    assert_equal(x[tup], x_js_buf.data[offset])
                assert_equal(minoffset, 0)
                assert_equal(maxoffset + 1, x_js_buf.length)
            x_js_buf.release()
        `);
        """
    )


def test_get_buffer_big_endian(selenium):
    selenium.run_js(
        """
        window.a = await pyodide.runPythonAsync(`
            import numpy as np
            np.arange(24, dtype="int16").byteswap().newbyteorder()
        `);
        """
    )
    with pytest.raises(
        Exception, match="Javascript has no native support for big endian buffers"
    ):
        selenium.run_js("a.getBuffer()")
    result = selenium.run_js(
        """
        let buf = a.getBuffer("i8")
        let result = Array.from(buf.data);
        buf.release();
        a.destroy();
        return result;
        """
    )
    assert len(result) == 48
    assert result[:18] == [0, 0, 0, 1, 0, 2, 0, 3, 0, 4, 0, 5, 0, 6, 0, 7, 0, 8]


def test_get_buffer_error_messages(selenium):
    with pytest.raises(Exception, match="Javascript has no Float16 support"):
        selenium.run_js(
            """
            await pyodide.runPythonAsync(`
                import numpy as np
                x = np.ones(2, dtype=np.float16)
            `);
            pyodide.pyimport("x").getBuffer();
            """
        )
