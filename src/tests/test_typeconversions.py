# See also test_pyproxy, test_jsproxy, and test_python.
import pytest


def test_python2js(selenium):
    assert selenium.run_js('return pyodide.runPython("None") === undefined')
    assert selenium.run_js('return pyodide.runPython("True") === true')
    assert selenium.run_js('return pyodide.runPython("False") === false')
    assert selenium.run_js('return pyodide.runPython("42") === 42')
    assert selenium.run_js('return pyodide.runPython("3.14") === 3.14')
    # Need to test all three internal string representations in Python: UCS1,
    # UCS2 and UCS4
    assert selenium.run_js('return pyodide.runPython("\'ascii\'") === "ascii"')
    assert selenium.run_js('return pyodide.runPython("\'ιωδιούχο\'") === "ιωδιούχο"')
    assert selenium.run_js('return pyodide.runPython("\'碘化物\'") === "碘化物"')
    assert selenium.run_js('return pyodide.runPython("\'🐍\'") === "🐍"')
    assert selenium.run_js(
        "let x = pyodide.runPython(\"b'bytes'\");\n"
        "return (x instanceof window.Uint8ClampedArray) && "
        "(x.length === 5) && "
        "(x[0] === 98)"
    )
    assert selenium.run_js(
        """
        let x = pyodide.runPython("[1, 2, 3]").deepCopyToJavascript();
        return ((x instanceof window.Array) && (x.length === 3) &&
                (x[0] == 1) && (x[1] == 2) && (x[2] == 3))
        """
    )
    assert selenium.run_js(
        """
        let x = pyodide.runPython("{42: 64}").deepCopyToJavascript();
        return (typeof x === "object") && (x[42] === 64)
        """
    )
    assert selenium.run_js(
        """
        let x = pyodide.runPython("open('/foo.txt', 'wb')")
        return (x.tell() === 0)
        """
    )


def test_python2js_long_ints(selenium):
    assert selenium.run("2**30") == 2 ** 30
    assert selenium.run("2**31") == 2 ** 31
    assert selenium.run("2**30 - 1 + 2**30") == (2 ** 30 - 1 + 2 ** 30)
    assert selenium.run("2**32 / 2**4") == (2 ** 32 / 2 ** 4)
    assert selenium.run("-2**30") == -(2 ** 30)
    assert selenium.run("-2**31") == -(2 ** 31)


def test_pythonexc2js(selenium):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js('return pyodide.runPython("5 / 0")')


def test_js2python(selenium):
    selenium.run_js(
        """
        window.jsstring_ucs1 = "pyodidé";
        window.jsstring_ucs2 = "碘化物";
        window.jsstring_ucs4 = "🐍";
        window.jsnumber0 = 42;
        window.jsnumber1 = 42.5;
        window.jsundefined = undefined;
        window.jsnull = null;
        window.jstrue = true;
        window.jsfalse = false;
        window.jsarray0 = [];
        window.jsarray1 = [1, 2, 3];
        window.jspython = pyodide.pyimport("open");
        window.jsbytes = new Uint8Array([1, 2, 3]);
        window.jsfloats = new Float32Array([1, 2, 3]);
        window.jsobject = new XMLHttpRequest();
        """
    )
    assert selenium.run("from js import jsstring_ucs1\n" 'jsstring_ucs1 == "pyodidé"')
    assert selenium.run("from js import jsstring_ucs2\n" 'jsstring_ucs2 == "碘化物"')
    assert selenium.run("from js import jsstring_ucs4\n" 'jsstring_ucs4 == "🐍"')
    assert selenium.run(
        "from js import jsnumber0\n" "jsnumber0 == 42 and isinstance(jsnumber0, int)"
    )
    assert selenium.run(
        "from js import jsnumber1\n"
        "jsnumber1 == 42.5 and isinstance(jsnumber1, float)"
    )
    assert selenium.run("from js import jsundefined\n" "jsundefined is None")
    assert selenium.run("from js import jstrue\n" "jstrue is True")
    assert selenium.run("from js import jsfalse\n" "jsfalse is False")
    assert selenium.run("from js import jspython\n" "jspython is open")
    assert selenium.run(
        """
        from js import jsbytes
        ((jsbytes.tolist() == [1, 2, 3])
         and (jsbytes.tobytes() == b"\x01\x02\x03"))
        """
    )
    assert selenium.run(
        """
        from js import jsfloats
        import struct
        expected = struct.pack("fff", 1, 2, 3)
        (jsfloats.tolist() == [1, 2, 3]) and (jsfloats.tobytes() == expected)
        """
    )
    assert selenium.run(
        "from js import jsobject\n" 'str(jsobject) == "[object XMLHttpRequest]"'
    )
    assert selenium.run(
        """
        from js import jsobject
        bool(jsobject) == True
        """
    )
    assert selenium.run(
        """
        from js import jsarray0
        bool(jsarray0) == False
        """
    )
    assert selenium.run(
        """
        from js import jsarray1
        bool(jsarray1) == True
        """
    )


def test_js2python_bool(selenium):
    selenium.run_js(
        """
        window.f = ()=>{}
        window.m0 = new Map();
        window.m1 = new Map([[0, 1]]);
        window.s0 = new Set();
        window.s1 = new Set([0]);
        """
    )
    assert (
        selenium.run(
            """
        from js import window, f, m0, m1, s0, s1
        [bool(x) for x in [f, m0, m1, s0, s1]]
        """
        )
        == [True, False, True, False, True]
    )


@pytest.mark.parametrize("wasm_heap", (False, True))
@pytest.mark.parametrize(
    "jstype, pytype",
    (
        ("Int8Array", "b"),
        ("Uint8Array", "B"),
        ("Uint8ClampedArray", "B"),
        ("Int16Array", "h"),
        ("Uint16Array", "H"),
        ("Int32Array", "i"),
        ("Uint32Array", "I"),
        ("Float32Array", "f"),
        ("Float64Array", "d"),
    ),
)
def test_typed_arrays(selenium, wasm_heap, jstype, pytype):
    if not wasm_heap:
        selenium.run_js(f"window.array = new {jstype}([1, 2, 3, 4]);\n")
    else:
        selenium.run_js(
            f"""
             let buffer = pyodide._module._malloc(
                   4 * {jstype}.BYTES_PER_ELEMENT);
             window.array = new {jstype}(
                   pyodide._module.HEAPU8.buffer, buffer, 4);
             window.array[0] = 1;
             window.array[1] = 2;
             window.array[2] = 3;
             window.array[3] = 4;
             """
        )
    assert selenium.run(
        f"""
         from js import array
         import struct
         expected = struct.pack("{pytype*4}", 1, 2, 3, 4)
         print(array.format, array.tolist(), array.tobytes())
         ((array.format == "{pytype}")
          and array.tolist() == [1, 2, 3, 4]
          and array.tobytes() == expected
          and array.obj._has_bytes() is {not wasm_heap})
         """
    )


def test_array_buffer(selenium):
    selenium.run_js("window.array = new ArrayBuffer(100);\n")
    assert (
        selenium.run(
            """
        from js import array
        len(array.tobytes())
        """
        )
        == 100
    )


def assert_js_to_py_to_js(selenium, name):
    selenium.run_js(f"window.obj = {name};")
    selenium.run("from js import obj")
    assert selenium.run_js("return pyodide.globals['obj'] === obj;")


def assert_py_to_js_to_py(selenium, name):
    selenium.run_js(f"window.obj = pyodide.globals['{name}'];")
    assert selenium.run(
        f"""
        from js import obj
        obj is {name}
        """
    )


def test_recursive_list_to_js(selenium_standalone):
    selenium_standalone.run(
        """
        x = []
        x.append(x)
        """
    )
    selenium_standalone.run_js("x = pyodide.pyimport('x').deepCopyToJavascript();")


def test_recursive_dict_to_js(selenium_standalone):
    selenium_standalone.run(
        """
        x = {}
        x[0] = x
        """
    )
    selenium_standalone.run_js("x = pyodide.pyimport('x').deepCopyToJavascript();")


def test_list_js2py2js(selenium):
    selenium.run_js("window.x = [1,2,3];")
    assert_js_to_py_to_js(selenium, "x")


def test_dict_js2py2js(selenium):
    selenium.run_js("window.x = { a : 1, b : 2, 0 : 3 };")
    assert_js_to_py_to_js(selenium, "x")


def test_error_js2py2js(selenium):
    selenium.run_js("window.err = new Error('hello there?');")
    assert_js_to_py_to_js(selenium, "err")


def test_error_py2js2py(selenium):
    selenium.run("err = Exception('hello there?');")
    assert_py_to_js_to_py(selenium, "err")


def test_list_py2js2py(selenium):
    selenium.run("x = ['a', 'b']")
    assert_py_to_js_to_py(selenium, "x")


def test_dict_py2js2py(selenium):
    selenium.run("x = {'a' : 5, 'b' : 1}")
    assert_py_to_js_to_py(selenium, "x")


def test_jsproxy_attribute_error(selenium):
    selenium.run_js(
        """
        class Point {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
        }
        window.point = new Point(42, 43);
        """
    )
    selenium.run(
        """
        from js import point
        assert point.y == 43
        """
    )

    msg = "AttributeError: z"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run("point.z")

    selenium.run("del point.y")
    msg = "AttributeError: y"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run("point.y")
    assert selenium.run_js("return point.y;") is None


def test_javascript_error(selenium):
    msg = "JsException: Error: This is a js error"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            from js import Error
            err = Error.new("This is a js error")
            err2 = Error.new("This is another js error")
            raise err
            """
        )


def test_javascript_error_back_to_js(selenium):
    selenium.run_js(
        """
        window.err = new Error("This is a js error");
        """
    )
    assert (
        selenium.run(
            """
        from js import err
        py_err = err
        type(py_err).__name__
        """
        )
        == "JsException"
    )
    assert selenium.run_js(
        """
        return pyodide.globals["py_err"] === err;
        """
    )


def test_memoryview_conversion(selenium):
    selenium.run(
        """
        import array
        a = array.array("Q", [1,2,3])
        b = array.array("u", "123")
        """
    )
    selenium.run_js(
        """
        pyodide.globals.a
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )

    selenium.run_js(
        """
        pyodide.globals.b
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )


def test_python2js_with_depth(selenium):

    selenium.run("a = [1, 2, 3]")
    assert selenium.run_js(
        """
        res = pyodide._module.test_python2js_with_depth("a", -1);
        return (Array.isArray(res)) && JSON.stringify(res) === "[1,2,3]";
        """
    )

    selenium.run("a = (1, 2, 3)")
    assert selenium.run_js(
        """
        res = pyodide._module.test_python2js_with_depth("a", -1);
        return (Array.isArray(res)) && JSON.stringify(res) === "[1,2,3]";
        """
    )

    selenium.run("a = [(1,2), (3,4), [5, 6], { 2 : 3,  4 : 9}]")
    assert selenium.run_js(
        """
        res = pyodide._module.test_python2js_with_depth("a", -1);
        return Array.isArray(res) && \
            JSON.stringify(res) === `[[1,2],[3,4],[5,6],{"2":3,"4":9}]`;
        """
    )

    selenium.run(
        """
        a = [1,[2,[3,[4,[5,[6,[7]]]]]]]
        """
    )
    selenium.run_js(
        """
        function assert(x, msg){
            if(x !== true){
                throw new Error(`Assertion failed: ${msg}`);
            }
        }
        for(let i=0; i < 7; i++){
            let x = pyodide._module.test_python2js_with_depth("a", i);
            for(let j=0; j < i; j++){
                assert(Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(pyodide._module.PyProxy.isPyProxy(x), `i: ${i}, j: ${i}`);
        }
        """
    )

    selenium.run("a = [1, (2, (3, [4, (5, (6, [7]))]))]")
    selenium.run_js(
        """
        function assert(x, msg){
            if(x !== true){
                throw new Error(`Assertion failed: ${msg}`);
            }
        }
        let depths = [0, 3, 3, 3, 6, 6, 6]
        for(let i=0; i < 7; i++){
            let x = pyodide._module.test_python2js_with_depth("a", i);
            for(let j=0; j < depths[i]; j++){
                assert(Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(pyodide._module.PyProxy.isPyProxy(x), `i: ${i}, j: ${i}`);
        }
        """
    )


@pytest.mark.xfail
def test_py2js_set(selenium):
    selenium.run("a = {1, 2, 3}")
    assert selenium.run_js(
        """
        let res = pyodide._module.test_python2js_with_depth("a", -1);
        return res instanceof Set;
        """
    )
