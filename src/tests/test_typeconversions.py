# See also test_pyproxy, test_jsproxy, and test_python.
import pytest
from hypothesis import given, settings, assume, strategies
from hypothesis.strategies import text, from_type
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


@given(
    n=strategies.one_of(
        strategies.integers(min_value=-(2 ** 53), max_value=2 ** 53),
        strategies.floats(allow_nan=False),
    )
)
@settings(deadline=600)
def test_number_conversions(selenium_module_scope, n):
    with selenium_context_manager(selenium_module_scope) as selenium:
        import json

        s = json.dumps(n)
        selenium.run_js(
            f"""
            window.x_js = eval({s!r}); // JSON.parse apparently doesn't work
            pyodide.runPython(`
                import json
                x_py = json.loads({s!r})
            `);
            """
        )
        assert selenium.run_js(f"""return pyodide.runPython('x_py') === x_js;""")
        assert selenium.run(
            """
            from js import x_js
            x_js == x_py
            """
        )


def test_nan_conversions(selenium):
    selenium.run_js(
        """
        window.a = NaN;
        pyodide.runPython(`
            from js import a
            from math import isnan, nan
            assert isnan(a)
        `);
        let b = pyodide.runPython("nan");
        if(!Number.isNaN(b)){
            throw new Error();
        }
        """
    )


@given(n=strategies.integers())
@settings(deadline=600)
def test_bigint_conversions(selenium_module_scope, n):
    with selenium_context_manager(selenium_module_scope) as selenium:
        h = hex(n)
        selenium.run_js(
            """
            window.assert = function assert(cb){
                if(cb() !== true){
                    throw new Error(`Assertion failed: ${cb.toString().slice(6)}`);
                }
            };
            """
        )
        selenium.run_js(f"window.h = {h!r};")
        selenium.run_js(
            """
            let negative = false;
            let h2 = h;
            if(h2.startsWith('-')){
                h2 = h2.slice(1);
                negative = true;
            }
            window.n = BigInt(h2);
            if(negative){
                window.n = -n;
            }
            pyodide.runPython(`
                from js import n, h
                n2 = int(h, 16)
                assert n == n2
            `);
            let n2 = pyodide.globals.get("n2");
            let n3 = Number(n2);
            if(Number.isSafeInteger(n3)){
                assert(() => typeof n2 === "number");
                assert(() => n2 === Number(n));
            } else {
                assert(() => typeof n2 === "bigint");
                assert(() => n2 === n);
            }
            """
        )


# Generate an object of any type
@given(obj=from_type(type).flatmap(from_type))
@settings(deadline=600)
def test_hyp_py2js2py(selenium_module_scope, obj):
    with selenium_context_manager(selenium_module_scope) as selenium:
        import pickle

        # When we compare x == x, there are three possible outcomes:
        # 1. returns True
        # 2. returns False (e.g., nan)
        # 3. raises an exception
        #
        # Hypothesis *will* test this function on objects in case 2 and 3, so we
        # have to defend against them here.
        try:
            assume(obj == obj)
        except:
            assume(False)
        try:
            obj_bytes = list(pickle.dumps(obj))
        except:
            assume(False)
        selenium.run(
            f"""
            import pickle
            x1 = pickle.loads(bytes({obj_bytes!r}))
            """
        )
        selenium.run_js(
            """
            window.x2 = pyodide.globals.get("x1");
            pyodide.runPython(`
                from js import x2
                if x1 != x2:
                    print(f"Assertion Error: {x1!r} != {x2!r}")
                    assert False
            `);
            """
        )


def test_big_integer_py2js2py(selenium):
    a = 9992361673228537
    selenium.run_js(
        f"""
        window.a = pyodide.runPython("{a}")
        pyodide.runPython(`
            from js import a
            assert a == {a}
        `);
        """
    )
    a = -a
    selenium.run_js(
        f"""
        window.a = pyodide.runPython("{a}")
        pyodide.runPython(`
            from js import a
            assert a == {a}
        `);
        """
    )


# Generate an object of any type
@given(obj=from_type(type).flatmap(from_type))
@settings(deadline=600)
def test_hyp_tojs_no_crash(selenium_module_scope, obj):
    with selenium_context_manager(selenium_module_scope) as selenium:
        import pickle

        try:
            obj_bytes = list(pickle.dumps(obj))
        except:
            assume(False)
        selenium.run(
            f"""
            import pickle
            x = pickle.loads(bytes({obj_bytes!r}))
            """
        )
        selenium.run_js(
            """
            let x = pyodide.globals.get("x");
            if(x && x.toJs){
                x.toJs();
            }
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
    assert selenium.run_js(
        "let x = pyodide.runPython(\"b'bytes'\").toJs();\n"
        "return (x instanceof window.Uint8Array) && "
        "(x.length === 5) && "
        "(x[0] === 98)"
    )
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


def test_wrong_way_conversions(selenium):
    selenium.run_js(
        """
        assert(() => pyodide.toPy(5) === 5);
        assert(() => pyodide.toPy(5n) === 5n);
        assert(() => pyodide.toPy("abc") === "abc");
        class Test {};
        let t = new Test();
        assert(() => pyodide.toPy(t) === t);

        window.a1 = [1,2,3];
        window.b1 = pyodide.toPy(a1);
        window.a2 = { a : 1, b : 2, c : 3};
        window.b2 = pyodide.toPy(a2);
        pyodide.runPython(`
            from js import a1, b1, a2, b2
            assert a1.to_py() == b1
            assert a2.to_py() == b2
        `);
        window.b1.destroy();
        window.b2.destroy();
        """
    )

    selenium.run_js(
        """
        window.a = [1,2,3];
        window.b = pyodide.runPython(`
            import pyodide
            pyodide.to_js([1, 2, 3])
        `);
        assert(() => JSON.stringify(a) == JSON.stringify(b));
        """
    )

    selenium.run_js(
        """
        window.t3 = pyodide.runPython(`
            class Test: pass
            t1 = Test()
            t2 = pyodide.to_js(t1)
            t2
        `);
        pyodide.runPython(`
            from js import t3
            assert t1 is t3
            t2.destroy();
        `);
        """
    )

    selenium.run_js(
        """
        pyodide.runPython(`
            s = "avafhjpa"
            t = 55
            assert pyodide.to_js(s) is s
            assert pyodide.to_js(t) is t
        `);
        """
    )


def test_python2js_long_ints(selenium):
    assert selenium.run("2**30") == 2 ** 30
    assert selenium.run("2**31") == 2 ** 31
    assert selenium.run("2**30 - 1 + 2**30") == (2 ** 30 - 1 + 2 ** 30)
    assert selenium.run("2**32 / 2**4") == (2 ** 32 / 2 ** 4)
    assert selenium.run("-2**30") == -(2 ** 30)
    assert selenium.run("-2**31") == -(2 ** 31)
    assert selenium.run_js(
        """
        return pyodide.runPython("2**64") === 2n**64n;
        """
    )
    assert selenium.run_js(
        """
        return pyodide.runPython("-(2**64)") === -(2n**64n);
        """
    )


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
        jsbytes = t.jsbytes.to_py()
        ((jsbytes.tolist() == [1, 2, 3])
         and (jsbytes.tobytes() == b"\x01\x02\x03"))
        """
    )
    assert selenium.run(
        """
        jsfloats = t.jsfloats.to_py()
        import struct
        expected = struct.pack("fff", 1, 2, 3)
        (jsfloats.tolist() == [1, 2, 3]) and (jsfloats.tobytes() == expected)
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
def test_typed_arrays(selenium, jstype, pytype):
    assert selenium.run_js(
        f"""
        window.array = new {jstype}([1, 2, 3, 4]);
        return pyodide.runPython(`
            from js import array
            array = array.to_py()
            import struct
            expected = struct.pack("{pytype*4}", 1, 2, 3, 4)
            print(array.format, array.tolist(), array.tobytes())
            # Result:
            ((array.format == "{pytype}")
            and array.tolist() == [1, 2, 3, 4]
            and array.tobytes() == expected)
        `);
        """
    )


def test_array_buffer(selenium):
    assert (
        selenium.run_js(
            """
            window.array = new ArrayBuffer(100);
            return pyodide.runPython(`
                from js import array
                array = array.to_py()
                len(array.tobytes())
            `);
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
            assert(pyodide.isPyProxy(x), `i: ${i}, j: ${i}`);
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
            assert(pyodide.isPyProxy(x), `i: ${i}, j: ${i}`);
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
