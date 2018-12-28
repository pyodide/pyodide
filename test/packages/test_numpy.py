def test_numpy(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    selenium.run("x = numpy.ones((32, 64))")
    assert selenium.run_js("return pyodide.pyimport('x').length == 32")
    for i in range(32):
        assert selenium.run_js(
            f"return pyodide.pyimport('x')[{i}].length == 64"
        )
        for j in range(64):
            assert selenium.run_js(
                f"return pyodide.pyimport('x')[{i}][{j}] == 1"
            )


def test_typed_arrays(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    for (jstype, npytype) in (
            ('Int8Array', 'int8'),
            ('Uint8Array', 'uint8'),
            ('Uint8ClampedArray', 'uint8'),
            ('Int16Array', 'int16'),
            ('Uint16Array', 'uint16'),
            ('Int32Array', 'int32'),
            ('Uint32Array', 'uint32'),
            ('Float32Array', 'float32'),
            ('Float64Array', 'float64')):
        print(jstype, npytype)
        selenium.run_js(
            f'window.array = new {jstype}([1, 2, 3, 4]);\n')
        assert selenium.run(
            'from js import array\n'
            'npyarray = numpy.asarray(array)\n'
            f'npyarray.dtype.name == "{npytype}" '
            'and npyarray == [1, 2, 3, 4]')
