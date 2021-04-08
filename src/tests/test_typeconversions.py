# See also test_pyproxy, test_jsproxy, and test_python.
import pytest
from hypothesis import given, settings
from hypothesis.strategies import text
from conftest import selenium_context_manager


@given(s=text())
@settings(deadline=600)
def test_string_conversion(selenium_module_scope, s):
    with selenium_context_manager(selenium_module_scope) as selenium:
        # careful string escaping here -- hypothesis will fuzz it.
        sbytes = list(s.encode())
        selenium.run_js(
            f"""
            window.sjs = (new TextDecoder("utf8")).decode(new Uint8Array({sbytes}));
            pyodide.runPython('spy = bytes({sbytes}).decode()');
            """
        )
        assert selenium.run_js(f"""return pyodide.runPython('spy') === sjs;""")
        assert selenium.run(
            """
            from js import sjs
            sjs == spy
            """
        )


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
    # TODO: replace with suitable test for the behavior of bytes objects once we
    # get the new behavior specified.
    # assert selenium.run_js(
    #     "let x = pyodide.runPython(\"b'bytes'\");\n"
    #     "return (x instanceof window.Uint8ClampedArray) && "
    #     "(x.length === 5) && "
    #     "(x[0] === 98)"
    # )
    assert selenium.run_js(
        """
        let proxy = pyodide.runPython("[1, 2, 3]");
        let typename = proxy.type;
        let x = proxy.toJs();
        proxy.destroy();
        return ((typename === "list") && (x instanceof window.Array) &&
                (x.length === 3) && (x[0] == 1) && (x[1] == 2) && (x[2] == 3));
        """
    )
    assert selenium.run_js(
        """
        let proxy = pyodide.runPython("{42: 64}");
        let typename = proxy.type;
        let x = proxy.toJs();
        proxy.destroy();
        return (typename === "dict") && (x.constructor.name === "Map") && (x.get(42) === 64)
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


def test_run_python_simple_error(selenium):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js("return pyodide._module.runPythonSimple('5 / 0');")


def test_js2python(selenium):
    selenium.run_js(
        """
        window.test_objects = {
            jsstring_ucs1 : "pyodidé",
            jsstring_ucs2 : "碘化物",
            jsstring_ucs4 : "🐍",
            jsnumber0 : 42,
            jsnumber1 : 42.5,
            jsundefined : undefined,
            jsnull : null,
            jstrue : true,
            jsfalse : false,
            jsarray0 : [],
            jsarray1 : [1, 2, 3],
            jspython : pyodide.globals.get("open"),
            jsbytes : new Uint8Array([1, 2, 3]),
            jsfloats : new Float32Array([1, 2, 3]),
            jsobject : new XMLHttpRequest(),
        };
        Object.assign(window, test_objects);
        """
    )
    selenium.run("from js import test_objects as t")
    assert selenium.run('t.jsstring_ucs1 == "pyodidé"')
    assert selenium.run('t.jsstring_ucs2 == "碘化物"')
    assert selenium.run('t.jsstring_ucs4 == "🐍"')
    assert selenium.run("t.jsnumber0 == 42 and isinstance(t.jsnumber0, int)")
    assert selenium.run("t.jsnumber1 == 42.5 and isinstance(t.jsnumber1, float)")
    assert selenium.run("t.jsundefined is None")
    assert selenium.run("t.jsnull is None")
    assert selenium.run("t.jstrue is True")
    assert selenium.run("t.jsfalse is False")
    assert selenium.run("t.jspython is open")
    assert selenium.run(
        """
        ((t.jsbytes.tolist() == [1, 2, 3])
         and (t.jsbytes.tobytes() == b"\x01\x02\x03"))
        """
    )
    assert selenium.run(
        """
        import struct
        expected = struct.pack("fff", 1, 2, 3)
        (t.jsfloats.tolist() == [1, 2, 3]) and (t.jsfloats.tobytes() == expected)
        """
    )
    assert selenium.run('str(t.jsobject) == "[object XMLHttpRequest]"')
    assert selenium.run("bool(t.jsobject) == True")
    assert selenium.run("bool(t.jsarray0) == False")
    assert selenium.run("bool(t.jsarray1) == True")


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
    assert selenium.run_js("return pyodide.globals.get('obj') === obj;")


def assert_py_to_js_to_py(selenium, name):
    selenium.run_js(f"window.obj = pyodide.globals.get('{name}');")
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
    selenium_standalone.run_js("x = pyodide.globals.get('x').toJs();")


def test_recursive_dict_to_js(selenium_standalone):
    selenium_standalone.run(
        """
        x = {}
        x[0] = x
        """
    )
    selenium_standalone.run_js("x = pyodide.globals.get('x').toJs();")


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
        return pyodide.globals.get("py_err") === err;
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
        pyodide.globals.get("a")
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )

    selenium.run_js(
        """
        pyodide.globals.get("b")
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )


def test_python2js_with_depth(selenium):
    assert selenium.run_js(
        """
        pyodide.runPython("a = [1, 2, 3]");
        let res = pyodide.globals.get("a").toJs();
        return (Array.isArray(res)) && JSON.stringify(res) === "[1,2,3]";
        """
    )

    assert selenium.run_js(
        """
        pyodide.runPython("a = (1, 2, 3)");
        let res = pyodide.globals.get("a").toJs();
        return (Array.isArray(res)) && JSON.stringify(res) === "[1,2,3]";
        """
    )

    assert selenium.run_js(
        """
        pyodide.runPython("a = [(1,2), (3,4), [5, 6], { 2 : 3,  4 : 9}]")
        let res = pyodide.globals.get("a").toJs();
        return Array.isArray(res) && \
            JSON.stringify(res) === `[[1,2],[3,4],[5,6],{}]` && \
            JSON.stringify(Array.from(res[3].entries())) === "[[2,3],[4,9]]";
        """
    )

    selenium.run_js(
        """
        window.assert = function assert(x, msg){
            if(x !== true){
                throw new Error(`Assertion failed: ${msg}`);
            }
        }
        """
    )

    selenium.run_js(
        """
        pyodide.runPython("a = [1,[2,[3,[4,[5,[6,[7]]]]]]]")
        let a = pyodide.globals.get("a");
        for(let i=0; i < 7; i++){
            let x = a.toJs(i);
            for(let j=0; j < i; j++){
                assert(Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(pyodide._module.PyProxy.isPyProxy(x), `i: ${i}, j: ${i}`);
        }
        """
    )

    selenium.run_js(
        """
        pyodide.runPython("a = [1, (2, (3, [4, (5, (6, [7]))]))]")
        function assert(x, msg){
            if(x !== true){
                throw new Error(`Assertion failed: ${msg}`);
            }
        }
        let a = pyodide.globals.get("a");
        for(let i=0; i < 7; i++){
            let x = a.toJs(i);
            for(let j=0; j < i; j++){
                assert(Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(pyodide._module.PyProxy.isPyProxy(x), `i: ${i}, j: ${i}`);
        }
        """
    )

    selenium.run_js(
        """
        pyodide.runPython(`
            a = [1, 2, 3, 4, 5]
            b = [a, a, a, a, a]
            c = [b, b, b, b, b]
        `);
        let total_refs = pyodide._module.hiwire.num_keys();
        let res = pyodide.globals.get("c").toJs();
        let new_total_refs = pyodide._module.hiwire.num_keys();
        assert(total_refs === new_total_refs);
        assert(res[0] === res[1]);
        assert(res[0][0] === res[1][1]);
        assert(res[4][0] === res[1][4]);
        """
    )

    selenium.run_js(
        """
        pyodide.runPython(`
            a = [["b"]]
            b = [1,2,3, a[0]]
            a[0].append(b)
            a.append(b)
        `);
        let total_refs = pyodide._module.hiwire.num_keys();
        let res = pyodide.globals.get("a").toJs();
        let new_total_refs = pyodide._module.hiwire.num_keys();
        assert(total_refs === new_total_refs);
        assert(res[0][0] === "b");
        assert(res[1][2] === 3);
        assert(res[1][3] === res[0]);
        assert(res[0][1] === res[1]);
        """
    )
    msg = "pyodide.ConversionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            pyodide.runPython(`
                { (2,2) : 0 }
            `).toJs()
            """
        )

    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            pyodide.runPython(`
                { (2,2) }
            `).toJs()
            """
        )

    assert (
        set(
            selenium.run_js(
                """
        return Array.from(pyodide.runPython(`
            { 1, "1" }
        `).toJs().values())
        """
            )
        )
        == {1, "1"}
    )

    assert (
        dict(
            selenium.run_js(
                """
        return Array.from(pyodide.runPython(`
            { 1 : 7, "1" : 9 }
        `).toJs().entries())
        """
            )
        )
        == {1: 7, "1": 9}
    )


def test_to_py(selenium):
    result = selenium.run_js(
        """
        window.a = new Map([[1, [1,2,new Set([1,2,3])]], [2, new Map([[1,2],[2,7]])]]);
        a.get(2).set("a", a);
        let result = [];
        for(let i = 0; i < 4; i++){
            result.push(pyodide.runPython(`
                from js import a
                repr(a.to_py(${i}))
            `));
        }
        return result;
        """
    )
    assert result == [
        "[object Map]",
        "{1: 1,2,[object Set], 2: [object Map]}",
        "{1: [1, 2, [object Set]], 2: {1: 2, 2: 7, 'a': [object Map]}}",
        "{1: [1, 2, {1, 2, 3}], 2: {1: 2, 2: 7, 'a': {...}}}",
    ]

    result = selenium.run_js(
        """
        window.a = { "x" : 2, "y" : 7, "z" : [1,2] };
        a.z.push(a);
        let result = [];
        for(let i = 0; i < 4; i++){
            result.push(pyodide.runPython(`
                from js import a
                repr(a.to_py(${i}))
            `));
        }
        return result;
        """
    )
    assert result == [
        "[object Object]",
        "{'x': 2, 'y': 7, 'z': 1,2,[object Object]}",
        "{'x': 2, 'y': 7, 'z': [1, 2, [object Object]]}",
        "{'x': 2, 'y': 7, 'z': [1, 2, {...}]}",
    ]

    result = selenium.run_js(
        """
        class Temp {
            constructor(){
                this.x = 2;
                this.y = 7;
            }
        }
        window.a = new Temp();
        let result = pyodide.runPython(`
            from js import a
            b = a.to_py()
            repr(type(b))
        `);
        return result;
        """
    )
    assert result == "<class 'pyodide.JsProxy'>"

    msg = "Cannot use key of type Array as a key to a Python dict"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Map([[[1,1], 2]]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )

    msg = "Cannot use key of type Array as a key to a Python set"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Set([[1,1]]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )

    msg = "contains both 0 and false"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Map([[0, 2], [false, 3]]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )

    msg = "contains both 1 and true"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Map([[1, 2], [true, 3]]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )

    msg = "contains both 0 and false"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Set([0, false]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )

    msg = "contains both 1 and true"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            window.a = new Set([1, true]);
            pyodide.runPython(`
                from js import a
                a.to_py()
            `);
            """
        )


def test_pyimport_deprecation(selenium):
    selenium.run_js("pyodide.runPython('x = 1')")
    assert selenium.run_js("return pyodide.pyimport('x') === 1")
    assert "pyodide.pyimport is deprecated and will be removed" in selenium.logs


def test_buffer_format_string(selenium):
    errors = [
        ["aaa", "Expected format string to have length <= 2, got 'aaa'"],
        ["II", "Unrecognized alignment character I."],
        ["x", "Unrecognized format character 'x'."],
        ["x", "Unrecognized format character 'x'."],
        ["e", "Javascript has no Float16 support."],
    ]
    for fmt, msg in errors:
        with pytest.raises(selenium.JavascriptException, match=msg):
            selenium.run_js(
                f"""
                pyodide._module.processBufferFormatString({fmt!r});
                """
            )

    format_tests = [
        ["c", "Uint8"],
        ["b", "Int8"],
        ["B", "Uint8"],
        ["?", "Uint8"],
        ["h", "Int16"],
        ["H", "Uint16"],
        ["i", "Int32"],
        ["I", "Uint32"],
        ["l", "Int32"],
        ["L", "Uint32"],
        ["n", "Int32"],
        ["N", "Uint32"],
        ["q", "BigInt64"],
        ["Q", "BigUint64"],
        ["f", "Float32"],
        ["d", "Float64"],
        ["s", "Uint8"],
        ["p", "Uint8"],
        ["P", "Uint32"],
    ]

    def process_fmt_string(fmt):
        return selenium.run_js(
            f"""
            let [array, is_big_endian] = pyodide._module.processBufferFormatString({fmt!r});
            if(!array || typeof array.name !== "string" || !array.name.endsWith("Array")){{
                throw new Error("Unexpected output on input {fmt}: " + array);
            }}
            let arrayName = array.name.slice(0, -"Array".length);
            return [arrayName, is_big_endian];
            """
        )

    for fmt, expected_array_name in format_tests:
        [array_name, is_big_endian] = process_fmt_string(fmt)
        assert not is_big_endian
        assert array_name == expected_array_name

    endian_tests = [
        ["@h", "Int16", False],
        ["=H", "Uint16", False],
        ["<i", "Int32", False],
        [">I", "Uint32", True],
        ["!l", "Int32", True],
    ]

    for fmt, expected_array_name, expected_is_big_endian in endian_tests:
        [array_name, is_big_endian] = process_fmt_string(fmt)
        assert is_big_endian == expected_is_big_endian
        assert array_name == expected_array_name
