# See also test_pyproxy, test_jsproxy, and test_python.
from typing import Any

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import text
from pytest_pyodide import run_in_pyodide
from pytest_pyodide.fixture import selenium_context_manager
from pytest_pyodide.hypothesis import (
    any_equal_to_self_strategy,
    any_strategy,
    std_hypothesis_settings,
)


@given(s=text())
@settings(deadline=10000)
@example("\ufeff")
def test_string_conversion(selenium_module_scope, s):
    @run_in_pyodide
    def main(selenium, sbytes):
        from pyodide.code import run_js

        run_js("self.encoder = new TextEncoder()")
        run_js("self.decoder = new TextDecoder('utf8', {ignoreBOM: true})")

        spy = bytes(sbytes).decode()
        sjs = run_js(
            """
            (sbytes) => {
                self.sjs = self.decoder.decode(new Uint8Array(sbytes));
                return sjs;
            }
            """
        )(sbytes)
        assert sjs == spy
        assert run_js("(spy) => spy === self.sjs")(spy)

    with selenium_context_manager(selenium_module_scope) as selenium:
        sbytes = list(s.encode())
        main(selenium, sbytes)


@given(s=text())
@std_hypothesis_settings
@example("\ufeff")
@run_in_pyodide
def test_string_conversion2(selenium, s):
    from pyodide.code import run_js

    run_js("self.encoder = new TextEncoder()")
    run_js("self.decoder = new TextDecoder('utf8', {ignoreBOM: true})")

    s_encoded = s.encode()
    sjs = run_js(
        """
        (s_encoded) => {
            let buf = s_encoded.getBuffer();
            self.sjs = self.decoder.decode(buf.data);
            buf.release();
            return sjs
        }
        """
    )(s_encoded)
    assert sjs == s
    assert run_js("""(spy) => spy === self.sjs""")(s)


def blns():
    import base64
    import json

    with open("./src/tests/blns.base64.json") as f:
        BLNS = json.load(f)
    for s in BLNS:
        yield base64.b64decode(s).decode(errors="ignore")


@pytest.mark.driver_timeout(60)
def test_string_conversion_blns(selenium):
    @run_in_pyodide
    def _string_conversion_blns_internal(selenium, s):
        from pyodide.code import run_js

        run_js("self.encoder = new TextEncoder()")
        run_js("self.decoder = new TextDecoder('utf8', {ignoreBOM: true})")

        s_encoded = s.encode()
        sjs = run_js(
            """
            (s_encoded) => {
                let buf = s_encoded.getBuffer();
                self.sjs = self.decoder.decode(buf.data);
                buf.release();
                return sjs
            }
            """
        )(s_encoded)
        assert sjs == s
        assert run_js("""(spy) => spy === self.sjs""")(s)

    strings = blns()
    for s in strings:
        _string_conversion_blns_internal(selenium, s)


@run_in_pyodide
def test_large_string_conversion(selenium):
    from pyodide.code import run_js

    longstr = run_js('"ab".repeat(200_000)')
    res = longstr.count("ab")
    assert res == 200_000
    run_js(
        """
        (s) => {
            assert(() => s.length === 40_000);
            for(let n = 0; n < 20_000; n++){
                assert(() => s.slice(2*n, 2*n+2) === "ab");
            }
        }
        """
    )("ab" * 20_000)


@given(
    n=st.one_of(
        st.integers(),
        st.floats(allow_nan=False),
    )
)
@std_hypothesis_settings
@example(2**53)
@example(2**53 - 1)
@example(2**53 + 1)
@example(-(2**53))
@example(-(2**53) - 1)
@example(-(2**53) + 1)
@run_in_pyodide
def test_number_conversions(selenium_module_scope, n):
    import json

    from pyodide.code import run_js

    x_js = run_js("(s) => self.x_js = eval(s)")(json.dumps(n))
    run_js("(x_py) => Number(x_py) === x_js")(n)

    if type(x_js) is float:
        assert x_js == float(n)
    else:
        assert x_js == n


@given(n=st.floats())
@std_hypothesis_settings
@run_in_pyodide
def test_number_conversions_2(selenium_module_scope, n):
    from pyodide.code import run_js

    assert run_js("(n) => typeof n")(n) == "number"
    from math import isinf, isnan

    if isnan(n):
        return
    import json

    n_js = run_js("(s) => eval(s)")(json.dumps(n))
    if not isinf(n) and float(int(n)) == n and -(2**53) < n < 2**53:
        assert isinstance(n_js, int)
    else:
        assert isinstance(n_js, float)


@given(n=st.integers())
@std_hypothesis_settings
@example(2**53)
@example(2**53 - 1)
@example(2**53 + 1)
@example(-(2**53))
@example(-(2**53) - 1)
@example(-(2**53) + 1)
@run_in_pyodide
def test_number_conversions_3(selenium_module_scope, n):
    from pyodide.code import run_js

    jsty = run_js("(n) => typeof n")(n)
    if -(2**53) + 1 < n < 2**53 - 1:
        assert jsty == "number"
    else:
        assert jsty == "bigint"
    import json

    n_js = run_js("(s) => eval(s)")(json.dumps(n))
    if -(2**53) < n < 2**53:
        assert isinstance(n_js, int)
    else:
        assert isinstance(n_js, float)


@run_in_pyodide
def test_nan_conversions(selenium):
    from pyodide.code import run_js

    jsnan = run_js("NaN")
    from math import isnan

    assert isnan(jsnan)
    assert run_js(
        """
        let mathmod = pyodide.pyimport("math");
        const res = Number.isNaN(mathmod.nan);
        mathmod.destroy();
        res
        """
    )


@given(n=st.integers())
@std_hypothesis_settings
def test_bigint_conversions(selenium_module_scope, n):
    with selenium_context_manager(selenium_module_scope) as selenium:
        h = hex(n)
        selenium.run_js(f"self.h = {h!r};")
        selenium.run_js(
            """
            let negative = false;
            let h2 = h;
            if(h2.startsWith('-')){
                h2 = h2.slice(1);
                negative = true;
            }
            self.n = BigInt(h2);
            if(negative){
                self.n = -n;
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


@given(
    n=st.one_of(
        st.integers(min_value=2**53 + 1),
        st.integers(max_value=-(2**53) - 1),
    )
)
@std_hypothesis_settings
def test_big_int_conversions2(selenium_module_scope, n):
    @run_in_pyodide
    def main(selenium, s):
        import json

        from pyodide.code import run_js

        x_py = json.loads(s)
        x_js, check = run_js(
            """
            (s, x_py) => {
                let x_js = eval(s + 'n');

                return [x_js, x_py === x_js];
            }
            """
        )(s, x_py)
        assert check
        assert x_js == x_py

    with selenium_context_manager(selenium_module_scope) as selenium:
        import json

        s = json.dumps(n)
        main(selenium, s)


@given(
    n=st.integers(),
    exp=st.integers(min_value=1, max_value=10),
)
@std_hypothesis_settings
def test_big_int_conversions3(selenium_module_scope, n, exp):
    @run_in_pyodide
    def main(selenium, s):
        import json

        from pyodide.code import run_js

        x_py = json.loads(s)
        x_js = run_js(
            f"""
            self.x_js = eval('{s}n'); // JSON.parse apparently doesn't work
            """
        )
        [x1, x2] = run_js(
            """
            (x_py) => [x_py.toString(), x_js.toString()]
            """
        )(x_py)
        assert x1 == x2

        check = run_js(
            """
            (x) => {
                const [a, b] = x.toJs();
                return a === b;
            }
            """
        )([str(x_js), str(x_py)])
        assert check

    with selenium_context_manager(selenium_module_scope) as selenium:
        val = 2 ** (32 * exp) - n
        import json

        s = json.dumps(val)
        main(selenium, s)


@given(obj=any_equal_to_self_strategy)
@std_hypothesis_settings
@run_in_pyodide
def test_hyp_py2js2py(selenium, obj):
    import __main__

    from pyodide.code import run_js

    __main__.obj = obj

    try:
        run_js('self.obj2 = pyodide.globals.get("obj"); 0;')
        from js import obj2  # type:ignore[attr-defined]

        assert obj2 == obj
        run_js(
            """
            if(self.obj2 && self.obj2.destroy){
                self.obj2.destroy();
            }
            delete self.obj2
            """
        )
    finally:
        del __main__.obj


@given(obj=any_equal_to_self_strategy)
@std_hypothesis_settings
@run_in_pyodide
def test_hyp_py2js2py_2(selenium, obj):
    import __main__

    from pyodide.code import run_js

    __main__.o = obj
    try:
        assert obj == run_js("pyodide.globals.get('o')")
    finally:
        del __main__.o


@pytest.mark.parametrize("a", [9992361673228537, -9992361673228537])
@run_in_pyodide
def test_big_integer_py2js2py(selenium, a):
    import __main__

    from pyodide.code import run_js

    __main__.a = a
    try:
        b = run_js("pyodide.globals.get('a')")
        assert a == b
    finally:
        del __main__.a


# Generate an object of any type
@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@given(obj=any_strategy)
@std_hypothesis_settings
@run_in_pyodide
def test_hyp_tojs_no_crash(selenium, obj):
    import __main__

    from pyodide.code import run_js

    __main__.x = obj
    try:
        run_js(
            """
            let x = pyodide.globals.get("x");
            if(x && x.toJs){
                x.toJs();
            }
            """
        )
    finally:
        del __main__.x


@pytest.mark.parametrize(
    "py,js",
    [
        (None, "undefined"),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        (3.14, "3.14"),
        # Need to test all three internal string representations in Python:
        # UCS1, UCS2 and UCS4
        ("ascii", "'ascii'"),
        ("ιωδιούχο", "'ιωδιούχο'"),
        ("碘化物", "'碘化物'"),
        ("🐍", "'🐍'"),
    ],
)
@run_in_pyodide
def test_python2js1(selenium, py, js):
    from pyodide.code import run_js

    assert run_js(
        f"""
        (py) => py === {js}
        """
    )(py)


@run_in_pyodide
def test_python2js2(selenium):
    from pyodide.code import run_js

    assert (
        list(
            run_js(
                """
                (x) => {
                    x = x.toJs();
                    return [x.constructor.name, x.length, x[0]];
                }
                """
            )(b"bytes")
        )
        == ["Uint8Array", 5, 98]
    )


@run_in_pyodide
def test_python2js3(selenium):
    from pyodide.code import run_js

    l = [7, 9, 13]
    result = run_js(
        """
        (proxy) => {
            x = proxy.toJs();
            return [proxy.type, x.constructor.name, x.length, x[0], x[1], x[2]]
        }
        """
    )(l)
    assert list(result) == ["list", "Array", 3, *l]


@run_in_pyodide
def test_python2js4(selenium):
    from pyodide.code import run_js

    assert (
        list(
            run_js(
                """
                (proxy) => {
                    let typename = proxy.type;
                    let x = proxy.toJs();
                    return [proxy.type, x.constructor.name, x.get(42)];
                }
                """
            )({42: 64})
        )
        == ["dict", "Map", 64]
    )


@run_in_pyodide
def test_python2js5(selenium):
    from pyodide.code import run_js

    assert run_js("(x) => x.tell()")(open("/foo.txt", "wb")) == 0

    from tempfile import TemporaryFile

    with TemporaryFile(mode="w+") as f:
        contents = ["a\n", "b\n", "hello there!\n"]
        f.writelines(contents)
        assert run_js("(f) => f.tell()")(f) == 17

        assert (
            run_js(
                """
                (f) => {
                    f.seek(0);
                    return [f.readline(), f.readline(), f.readline()];
                }
                """
            )(f).to_py()
            == contents
        )


def test_python2js_track_proxies(selenium):
    selenium.run_js(
        """
        let x = pyodide.runPython(`
            class T:
                pass
            [[T()],[T()], [[[T()],[T()]],[T(), [], [[T()]], T()], T(), T()], T()]
        `);
        let proxies = [];
        let result = x.toJs({ pyproxies : proxies });
        assert(() => proxies.length === 10);
        for(let x of proxies){
            x.destroy();
        }
        function check(l){
            for(let x of l){
                if(pyodide.isPyProxy(x)){
                    assert(() => x.$$.ptr === 0);
                } else {
                    check(x);
                }
            }
        }
        check(result);
        assertThrows(() => x.toJs({create_pyproxies : false}), "PythonError", "pyodide.ffi.ConversionError");
        x.destroy();
        """
    )


@run_in_pyodide
def test_wrong_way_track_proxies(selenium):
    from pyodide.code import run_js

    checkDestroyed = run_js(
        """
        function checkDestroyed(l){
            for(let e of l){
                if(pyodide.isPyProxy(e)){
                    console.log("\\n\\n", "!!!!!!!!!", e.$$.ptr);
                    assert(() => e.$$.ptr === 0);
                } else {
                    checkDestroyed(e);
                }
            }
        };
        checkDestroyed
        """
    )
    from unittest import TestCase

    from js import Array, Object
    from pyodide.ffi import ConversionError, destroy_proxies, to_js

    raises = TestCase().assertRaises

    class T:
        pass

    x = [[T()], [T()], [[[T()], [T()]], [T(), [], [[T()]], T()], T(), T()], T()]
    proxylist = Array.new()
    r = to_js(x, pyproxies=proxylist)
    assert len(proxylist) == 10
    destroy_proxies(proxylist)
    checkDestroyed(r)
    with raises(TypeError):
        to_js(x, pyproxies=[])  # type:ignore[call-overload]
    with raises(TypeError):
        to_js(x, pyproxies=Object.new())
    with raises(ConversionError):
        to_js(x, create_pyproxies=False)


def test_wrong_way_conversions1(selenium):
    selenium.run_js(
        """
        assert(() => pyodide.toPy(5) === 5);
        assert(() => pyodide.toPy(5n) === 5n);
        assert(() => pyodide.toPy("abc") === "abc");
        class Test {};
        let t = new Test();
        assert(() => pyodide.toPy(t) === t);

        self.a1 = [1,2,3];
        self.b1 = pyodide.toPy(a1);
        self.a2 = { a : 1, b : 2, c : 3};
        self.b2 = pyodide.toPy(a2);
        pyodide.runPython(`
            from js import a1, b1, a2, b2
            assert a1.to_py() == b1
            assert a2.to_py() == b2
        `);
        self.b1.destroy();
        self.b2.destroy();
        """
    )


@run_in_pyodide
def test_wrong_way_conversions2(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    [astr, bstr] = run_js(
        """
        (a) => {
            b = [1,2,3];
            return [JSON.stringify(a), JSON.stringify(b)]
        }
        """
    )(to_js([1, 2, 3]))
    assert astr == bstr


@run_in_pyodide
def test_wrong_way_conversions3(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    class Test:
        pass

    t1 = Test()
    t2 = to_js(t1)
    t3 = run_js("(t2) => t2.copy()")(t2)

    assert t1 is t3
    t2.destroy()


@run_in_pyodide
def test_wrong_way_conversions4(selenium):
    from pyodide.ffi import to_js

    s = "avafhjpa"
    t = 55
    assert to_js(s) is s
    assert to_js(t) is t


@run_in_pyodide
def test_dict_converter1(selenium):
    import json

    from pyodide.code import run_js
    from pyodide.ffi import to_js

    arrayFrom = run_js("Array.from")
    d = {x: x + 2 for x in range(5)}
    res = to_js(d, dict_converter=arrayFrom)
    constructor, serialized = run_js(
        """
        (res) => {
            return [res.constructor.name, JSON.stringify(res)];
        }
        """
    )(res)

    assert constructor == "Array"
    assert json.loads(serialized) == [list(x) for x in d.items()]


@run_in_pyodide
def test_dict_converter2(selenium):
    import json

    from pyodide.code import run_js

    d = {x: x + 2 for x in range(5)}
    constructor, serialized = run_js(
        """
        (d) => {
            const res = d.toJs({dict_converter : Array.from});
            return [res.constructor.name, JSON.stringify(res)];
        }
        """
    )(d)

    assert constructor == "Array"
    assert json.loads(serialized) == [list(x) for x in d.items()]


@run_in_pyodide
def test_dict_converter3(selenium):
    import json

    from js import Object
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    d = {x: x + 2 for x in range(5)}

    res = to_js(d, dict_converter=Object.fromEntries)
    constructor, serialized = run_js(
        """
        (res) => [res.constructor.name, JSON.stringify(res)]
        """
    )(res)

    assert constructor == "Object"
    assert json.loads(serialized) == {str(k): v for k, v in d.items()}


@run_in_pyodide
def test_dict_converter4(selenium):
    import json

    from pyodide.code import run_js

    d = {x: x + 2 for x in range(5)}

    constructor, serialized = run_js(
        """
        (px) => {
            let res = px.toJs({dict_converter : Object.fromEntries});
            return [res.constructor.name, JSON.stringify(res)];
        }
        """
    )(d)

    assert constructor == "Object"
    assert json.loads(serialized) == {str(k): v for k, v in d.items()}


@pytest.mark.parametrize(
    "formula",
    ["2**30", "2**31", "2**30 - 1 + 2**30", "2**32 / 2**4", "-2**30", "-2**31"],
)
def test_python2js_long_ints(selenium, formula):
    assert selenium.run(formula) == eval(formula)


@run_in_pyodide
def test_python2js_long_ints2(selenium):
    from pyodide.code import run_js

    assert run_js(
        """
        (x) => x === 2n**64n;
        """
    )(2**64)

    assert run_js(
        """
        (x) => x === -(2n**64n);
        """
    )(-(2**64))


def test_pythonexc2js(selenium):
    msg = "ZeroDivisionError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js('return pyodide.runPython("5 / 0")')


def test_js2python(selenium):
    selenium.run_js(
        """
        self.test_objects = {
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
            jsobject : new TextDecoder(),
        };
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
    assert selenium.run('str(t.jsobject) == "[object TextDecoder]"')
    assert selenium.run("bool(t.jsobject) == True")
    assert selenium.run("bool(t.jsarray0) == False")
    assert selenium.run("bool(t.jsarray1) == True")
    selenium.run_js("test_objects.jspython.destroy()")


@pytest.mark.parametrize(
    "jsval, is_truthy",
    [
        ("()=>{}", True),
        ("new Map()", False),
        ("new Map([[0, 1]])", True),
        ("new Set()", False),
        ("new Set([0])", True),
    ],
)
@run_in_pyodide
def test_js2python_bool(selenium, jsval, is_truthy):
    from pyodide.code import run_js

    assert bool(run_js(jsval)) is is_truthy


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
@run_in_pyodide
def test_typed_arrays(selenium, jstype, pytype):
    from pyodide.code import run_js

    array = run_js(f"new {jstype}([1, 2, 3, 4]);").to_py()
    print(array.format, array.tolist(), array.tobytes())
    assert array.format == pytype
    assert array.tolist() == [1, 2, 3, 4]
    import struct

    assert array.tobytes() == struct.pack(pytype * 4, 1, 2, 3, 4)


@run_in_pyodide
def test_array_buffer(selenium):
    from pyodide.code import run_js

    array = run_js("new ArrayBuffer(100);").to_py()
    assert len(array.tobytes()) == 100


def assert_js_to_py_to_js(selenium, name):
    selenium.run_js(f"self.obj = {name};")
    selenium.run("from js import obj")
    assert selenium.run_js(
        """
        let pyobj = pyodide.globals.get("obj");
        return pyobj === obj;
        """
    )


def assert_py_to_js_to_py(selenium, name):
    selenium.run_js(
        f"""
        self.obj = pyodide.runPython('{name}');
        pyodide.runPython(`
            from js import obj
            assert obj is {name}
        `);
        obj.destroy();
        """
    )


@run_in_pyodide
def test_recursive_list_to_js(selenium):
    x: Any = []
    x.append(x)
    from pyodide.ffi import to_js

    to_js(x)


@run_in_pyodide
def test_recursive_dict_to_js(selenium):
    x: Any = {}
    x[0] = x
    from pyodide.ffi import to_js

    to_js(x)


def test_list_js2py2js(selenium):
    selenium.run_js("self.x = [1,2,3];")
    assert_js_to_py_to_js(selenium, "x")


def test_dict_js2py2js(selenium):
    selenium.run_js("self.x = { a : 1, b : 2, 0 : 3 };")
    assert_js_to_py_to_js(selenium, "x")


def test_error_js2py2js(selenium):
    selenium.run_js("self.err = new Error('hello there?');")
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


@run_in_pyodide
def test_jsproxy_attribute_error(selenium):
    import pytest

    from pyodide.code import run_js

    point = run_js(
        """
        class Point {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
        }
        new Point(42, 43);
        """
    )
    assert point.y == 43

    with pytest.raises(AttributeError, match="z"):
        point.z

    del point.y
    with pytest.raises(AttributeError, match="y"):
        point.y

    assert run_js("(point) => point.y;")(point) is None


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


@run_in_pyodide
def test_javascript_error_back_to_js(selenium):
    from pyodide.code import run_js

    err = run_js('self.err = new Error("This is a js error"); err')
    assert type(err).__name__ == "JsException"
    assert run_js(
        """
        (py_err) => py_err === err;
        """
    )(err)


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
        pyodide.runPython("a").destroy()
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )

    selenium.run_js(
        """
        pyodide.runPython("b").destroy()
        // Implicit assertion: this doesn't leave python error indicator set
        // (automatically checked in conftest.py)
        """
    )


def test_python2js_with_depth(selenium):
    selenium.run_js(
        """
        let x = pyodide.runPython(`
            class Test: pass
            [Test(), [Test(), [Test(), [Test()]]]]
        `);
        let Module = pyodide._module;
        let proxies = [];
        let proxies_id = Module.hiwire.new_value(proxies);
        let result = Module.hiwire.pop_value(Module._python2js_with_depth(x.$$.ptr, -1, proxies_id));
        Module.hiwire.decref(proxies_id);

        assert(() => proxies.length === 4);

        let result_proxies = [result[0], result[1][0], result[1][1][0], result[1][1][1][0]];
        proxies.sort((x, y) => x.$$.ptr < y.$$.ptr);
        result_proxies.sort((x, y) => x.$$.ptr < y.$$.ptr);
        for(let i = 0; i < 4; i++){
            assert(() => proxies[i] == result_proxies[i]);
        }
        x.destroy();
        for(let px of proxies){
            px.destroy();
        }
        """
    )


@pytest.mark.parametrize("ty", [list, tuple])
@run_in_pyodide
def test_tojs1(selenium, ty):
    import json

    from pyodide.code import run_js

    l = [1, 2, 3]
    x = ty(l)
    assert run_js("x => Array.isArray(x.toJs())")(x)
    serialized = run_js("x => JSON.stringify(x.toJs())")(x)
    assert l == json.loads(serialized)


@run_in_pyodide
def test_tojs2(selenium):
    import json

    from pyodide.code import run_js

    o = [(1, 2), (3, 4), [5, 6], {2: 3, 4: 9}]

    assert run_js("(o) => Array.isArray(o.toJs())")(o)
    serialized = run_js("(o) => JSON.stringify(o.toJs())")(o)
    assert json.loads(serialized) == [[1, 2], [3, 4], [5, 6], {}]
    serialized = run_js("(o) => JSON.stringify(Array.from(o.toJs()[3].entries()))")(o)
    assert json.loads(serialized) == [[2, 3], [4, 9]]


def test_tojs4(selenium):
    selenium.run_js(
        """
        let a = pyodide.runPython("[1,[2,[3,[4,[5,[6,[7]]]]]]]")
        for(let i=0; i < 7; i++){
            let x = a.toJs({depth : i});
            for(let j=0; j < i; j++){
                assert(() => Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(() => pyodide.isPyProxy(x), `i: ${i}, j: ${i}`);
            x.destroy();
        }
        a.destroy()
        """
    )


def test_tojs5(selenium):
    selenium.run_js(
        """
        let a = pyodide.runPython("[1, (2, (3, [4, (5, (6, [7]))]))]")
        for(let i=0; i < 7; i++){
            let x = a.toJs({depth : i});
            for(let j=0; j < i; j++){
                assert(() => Array.isArray(x), `i: ${i}, j: ${j}`);
                x = x[1];
            }
            assert(() => pyodide.isPyProxy(x), `i: ${i}, j: ${i}`);
            x.destroy();
        }
        a.destroy()
        """
    )


def test_tojs6(selenium):
    selenium.run_js(
        """
        let respy = pyodide.runPython(`
            a = [1, 2, 3, 4, 5]
            b = [a, a, a, a, a]
            [b, b, b, b, b]
        `);
        let total_refs = pyodide._module.hiwire.num_keys();
        let res = respy.toJs();
        let new_total_refs = pyodide._module.hiwire.num_keys();
        respy.destroy();
        assert(() => total_refs === new_total_refs);
        assert(() => res[0] === res[1]);
        assert(() => res[0][0] === res[1][1]);
        assert(() => res[4][0] === res[1][4]);
        """
    )


def test_tojs7(selenium):
    selenium.run_js(
        """
        let respy = pyodide.runPython(`
            a = [["b"]]
            b = [1,2,3, a[0]]
            a[0].append(b)
            a.append(b)
            a
        `);
        let total_refs = pyodide._module.hiwire.num_keys();
        let res = respy.toJs();
        let new_total_refs = pyodide._module.hiwire.num_keys();
        respy.destroy();
        assert(() => total_refs === new_total_refs);
        assert(() => res[0][0] === "b");
        assert(() => res[1][2] === 3);
        assert(() => res[1][3] === res[0]);
        assert(() => res[0][1] === res[1]);
        """
    )


@pytest.mark.skip_pyproxy_check
@run_in_pyodide
def test_tojs8(selenium):
    import pytest

    from pyodide.ffi import ConversionError, to_js

    msg = r"Cannot use \(2, 2\) as a key for a Javascript"
    with pytest.raises(ConversionError, match=msg):
        to_js({(2, 2): 0})

    with pytest.raises(ConversionError, match=msg):
        to_js({(2, 2)})


def test_tojs9(selenium):
    assert (
        set(
            selenium.run_js(
                """
                return Array.from(pyodide.runPython(`
                    from pyodide.ffi import to_js
                    to_js({ 1, "1" })
                `).values())
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
                    from pyodide.ffi import to_js
                    to_js({ 1 : 7, "1" : 9 })
                `).entries())
                """
            )
        )
        == {1: 7, "1": 9}
    )


@run_in_pyodide
def test_to_py1(selenium):
    from pyodide.code import run_js

    a = run_js(
        """
        let a = new Map([[1, [1,2,new Set([1,2,3])]], [2, new Map([[1,2],[2,7]])]]);
        a.get(2).set("a", a);
        a;
        """
    )
    result = [repr(a.to_py(depth=i)) for i in range(4)]
    assert result == [
        "[object Map]",
        "{1: 1,2,[object Set], 2: [object Map]}",
        "{1: [1, 2, [object Set]], 2: {1: 2, 2: 7, 'a': [object Map]}}",
        "{1: [1, 2, {1, 2, 3}], 2: {1: 2, 2: 7, 'a': {...}}}",
    ]


@run_in_pyodide
def test_to_py2(selenium):
    from pyodide.code import run_js

    a = run_js(
        """
        let a = { "x" : 2, "y" : 7, "z" : [1,2] };
        a.z.push(a);
        a
        """
    )
    result = [repr(a.to_py(depth=i)) for i in range(4)]
    assert result == [
        "[object Object]",
        "{'x': 2, 'y': 7, 'z': 1,2,[object Object]}",
        "{'x': 2, 'y': 7, 'z': [1, 2, [object Object]]}",
        "{'x': 2, 'y': 7, 'z': [1, 2, {...}]}",
    ]


@run_in_pyodide
def test_to_py3(selenium):
    from pyodide.code import run_js

    a = run_js(
        """
        class Temp {
            constructor(){
                this.x = 2;
                this.y = 7;
            }
        }
        new Temp();
        """
    )
    assert repr(type(a.to_py())) == "<class 'pyodide.JsProxy'>"


@pytest.mark.parametrize(
    "obj, msg",
    [
        ("Map([[[1,1], 2]])", "Cannot use key of type Array as a key to a Python dict"),
        ("Set([[1,1]])", "Cannot use key of type Array as a key to a Python set"),
        ("Map([[0, 2], [false, 3]])", "contains both 0 and false"),
        ("Set([0, false])", "contains both 0 and false"),
        ("Map([[1, 2], [true, 3]])", "contains both 1 and true"),
        ("Set([1, true])", "contains both 1 and true"),
    ],
)
@run_in_pyodide
def test_to_py4(selenium, obj, msg):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import ConversionError, JsException

    a = run_js(f"new {obj}")

    with pytest.raises((ConversionError, JsException), match=msg):
        a.to_py()


@run_in_pyodide
def test_to_py_default_converter(selenium):
    from pyodide.code import run_js

    [r1, r2] = run_js(
        """
        class Pair {
            constructor(first, second){
                this.first = first;
                this.second = second;
            }
        }
        let l = [1,2,3];
        const r1 = new Pair(l, [l]);
        const r2 = new Pair(l, [l]);
        r2.first = r2;
        const opts = {defaultConverter(value, converter, cache){
            if(value.constructor.name !== "Pair"){
                return value;
            }
            let list = pyodide.globals.get("list");
            l = list();
            list.destroy();
            cache(value, l);
            const first = converter(value.first);
            const second = converter(value.second);
            l.append(first);
            l.append(second);
            first.destroy();
            second.destroy();
            return l;
        }};
        pyodide.toPy([r1, r2], opts);
        """
    )

    assert isinstance(r1, list)
    assert r1[0] is r1[1][0]
    assert r1[0] == [1, 2, 3]
    assert r2[0] is r2


@run_in_pyodide
def test_to_py_default_converter2(selenium):
    from typing import Any

    from pyodide.code import run_js

    [p1, p2] = run_js(
        """
        class Pair {
            constructor(first, second){
                this.first = first;
                this.second = second;
            }
        }
        const l = [1,2,3];
        const r1 = new Pair(l, [l]);
        const r2 = new Pair(l, [l]);
        r2.first = r2;
        [r1, r2]
        """
    )

    def default_converter(value, converter, cache):
        if value.constructor.name != "Pair":
            return value
        l: list[Any] = []
        cache(value, l)
        l.append(converter(value.first))
        l.append(converter(value.second))
        return l

    r1 = p1.to_py(default_converter=default_converter)
    assert isinstance(r1, list)
    assert r1[0] is r1[1][0]
    assert r1[0] == [1, 2, 3]

    r2 = p2.to_py(default_converter=default_converter)
    assert r2[0] is r2


def test_to_js_default_converter(selenium):
    selenium.run_js(
        """
        p = pyodide.runPython(`
        class Pair:
            def __init__(self, first, second):
                self.first = first
                self.second = second
        p = Pair(1,2)
        p
        `);
        let res = p.toJs({ default_converter(x, convert, cacheConversion){
            let result = [];
            cacheConversion(x, result);
            result.push(convert(x.first));
            result.push(convert(x.second));
            return result;
        }});
        assert(() => res[0] === 1);
        assert(() => res[1] === 2);
        p.first = p;
        let res2 = p.toJs({ default_converter(x, convert, cacheConversion){
            let result = [];
            cacheConversion(x, result);
            result.push(convert(x.first));
            result.push(convert(x.second));
            return result;
        }});
        assert(() => res2[0] === res2);
        assert(() => res2[1] === 2);
        p.destroy();
        """
    )


@run_in_pyodide
def test_to_js_default_converter2(selenium):
    import json

    import pytest

    from js import JSON, Array
    from pyodide.code import run_js
    from pyodide.ffi import JsException, to_js

    class Pair:
        __slots__ = ("first", "second")

        def __init__(self, first, second):
            self.first = first
            self.second = second

    p1 = Pair(1, 2)
    p2 = Pair(1, 2)
    p2.first = p2

    def default_converter(value, convert, cacheConversion):
        result = Array.new()
        cacheConversion(value, result)
        result.push(convert(value.first))
        result.push(convert(value.second))
        return result

    p1js = to_js(p1, default_converter=default_converter)
    p2js = to_js(p2, default_converter=default_converter)

    assert json.loads(JSON.stringify(p1js)) == [1, 2]

    with pytest.raises(JsException, match="TypeError"):
        JSON.stringify(p2js)

    assert run_js("(x) => x[0] === x")(p2js)
    assert run_js("(x) => x[1] === 2")(p2js)


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
        ("c", "Uint8"),
        ("b", "Int8"),
        ("B", "Uint8"),
        ("?", "Uint8"),
        ("h", "Int16"),
        ("H", "Uint16"),
        ("i", "Int32"),
        ("I", "Uint32"),
        ("l", "Int32"),
        ("L", "Uint32"),
        ("n", "Int32"),
        ("N", "Uint32"),
        ("q", "BigInt64"),
        ("Q", "BigUint64"),
        ("f", "Float32"),
        ("d", "Float64"),
        ("s", "Uint8"),
        ("p", "Uint8"),
        ("P", "Uint32"),
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
        ("@h", "Int16", False),
        ("=H", "Uint16", False),
        ("<i", "Int32", False),
        (">I", "Uint32", True),
        ("!l", "Int32", True),
    ]

    for fmt, expected_array_name, expected_is_big_endian in endian_tests:
        [array_name, is_big_endian] = process_fmt_string(fmt)
        assert is_big_endian == expected_is_big_endian
        assert array_name == expected_array_name


def test_dict_converter_cache(selenium):
    selenium.run_js(
        """
        let d1 = pyodide.runPython('d={0: {1: 2}}; d[1]=d[0]; d');
        let d = d1.toJs({dict_converter: Object.fromEntries});
        d1.destroy();
        assert(() => d[0] === d[1]);
        """
    )


@pytest.mark.parametrize("n", [1 << 31, 1 << 32, 1 << 33, 1 << 63, 1 << 64, 1 << 65])
@run_in_pyodide
def test_very_large_length(selenium, n):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises(
        OverflowError, msg=f"length {n} of object is larger than INT_MAX (2147483647)"
    )

    o = run_js(f"({{length : {n}}})")
    with raises:
        len(o)

    # 1. Set toStringTag to NodeList to force JsProxy to feature detect this object
    # as an array
    # 2. Return a very large length
    # 3. JsProxy_subscript_array should successfully handle this and propagate the error.
    a = run_js(f"({{[Symbol.toStringTag] : 'NodeList', length: {n}}})")
    with raises:
        a[-1]


@pytest.mark.parametrize(
    "n", [-1, -2, -3, -100, -1 << 31, -1 << 32, -1 << 33, -1 << 63, -1 << 64, -1 << 65]
)
@run_in_pyodide
def test_negative_length(selenium, n):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises(
        ValueError, msg=f"length {n} of object is negative"
    )

    o = run_js(f"({{length : {n}}})")
    with raises:
        len(o)

    # 1. Set toStringTag to NodeList to force JsProxy to feature detect this object
    # as an array
    # 2. Return a negative length
    # 3. JsProxy_subscript_array should successfully handle this and propagate the error.
    a = run_js(f"({{[Symbol.toStringTag] : 'NodeList', length: {n}}})")
    with raises:
        a[-1]


@std_hypothesis_settings
@given(l=st.lists(st.integers()), slice=st.slices(50))
@example(l=[0, 1], slice=slice(None, None, -1))
@example(l=list(range(4)), slice=slice(None, None, -2))
@example(l=list(range(10)), slice=slice(-1, 12))
@example(l=list(range(10)), slice=slice(12, -1))
@example(l=list(range(10)), slice=slice(12, -1, -1))
@example(l=list(range(10)), slice=slice(-1, 12, 2))
@example(l=list(range(10)), slice=slice(12, -1, -1))
@example(l=list(range(10)), slice=slice(12, -1, -2))
@run_in_pyodide
def test_array_slices(selenium, l, slice):
    expected = l[slice]
    from pyodide.ffi import JsArray, to_js

    jsl = to_js(l)
    assert isinstance(jsl, JsArray)
    result = jsl[slice]
    assert result.to_py() == expected


@std_hypothesis_settings
@given(l=st.lists(st.integers()), slice=st.slices(50))
@example(l=[0, 1], slice=slice(None, None, -1))
@example(l=list(range(4)), slice=slice(None, None, -2))
@example(l=list(range(10)), slice=slice(-1, 12))
@example(l=list(range(10)), slice=slice(12, -1))
@example(l=list(range(10)), slice=slice(12, -1, -1))
@example(l=list(range(10)), slice=slice(-1, 12, 2))
@example(l=list(range(10)), slice=slice(12, -1, -1))
@example(l=list(range(10)), slice=slice(12, -1, -2))
@run_in_pyodide
def test_array_slice_del(selenium, l, slice):
    from pyodide.ffi import JsArray, to_js

    jsl = to_js(l)
    assert isinstance(jsl, JsArray)
    del l[slice]
    del jsl[slice]
    assert jsl.to_py() == l


@st.composite
def list_slice_and_value(draw):
    l = draw(st.lists(st.integers()))
    step_one = draw(st.booleans())
    if step_one:
        start = draw(st.integers(0, max(len(l) - 1, 0)) | st.none())
        stop = draw(st.integers(start, len(l)) | st.none())
        if draw(st.booleans()) and start is not None:
            start -= len(l)
        if draw(st.booleans()) and stop is not None:
            stop -= len(l)
        s = slice(start, stop)
        vals = draw(st.lists(st.integers()))
    else:
        s = draw(st.slices(50))
        vals_len = len(l[s])
        vals = draw(st.lists(st.integers(), min_size=vals_len, max_size=vals_len))
    return (l, s, vals)


@std_hypothesis_settings
@given(lsv=list_slice_and_value())
@example(lsv=(list(range(5)), slice(5, 2), []))
@example(lsv=(list(range(5)), slice(2, 5, -1), []))
@example(lsv=(list(range(5)), slice(5, 2), [-1, -2, -3]))
@run_in_pyodide
def test_array_slice_assign_1(selenium, lsv):
    from pyodide.ffi import JsArray, to_js

    [l, s, v] = lsv
    jsl = to_js(l)
    assert isinstance(jsl, JsArray)
    l[s] = v
    jsl[s] = v
    assert jsl.to_py() == l


@run_in_pyodide
def test_array_slice_assign_2(selenium):
    import pytest

    from pyodide.ffi import JsArray, to_js

    l = list(range(10))
    with pytest.raises(ValueError) as exc_info_1a:
        l[0:4:2] = [1, 2, 3, 4]

    jsl = to_js(l)
    assert isinstance(jsl, JsArray)
    with pytest.raises(ValueError) as exc_info_1b:
        jsl[0:4:2] = [1, 2, 3, 4]

    l = list(range(10))
    with pytest.raises(ValueError) as exc_info_2a:
        l[0:4:2] = []

    with pytest.raises(ValueError) as exc_info_2b:
        jsl[0:4:2] = []

    with pytest.raises(TypeError) as exc_info_3a:
        l[:] = 1  # type: ignore[call-overload]

    with pytest.raises(TypeError) as exc_info_3b:
        jsl[:] = 1

    assert exc_info_1a.value.args == exc_info_1b.value.args
    assert exc_info_2a.value.args == exc_info_2b.value.args
    assert exc_info_3a.value.args == exc_info_3b.value.args


@std_hypothesis_settings
@given(l1=st.lists(st.integers()), l2=st.lists(st.integers()))
@example(l1=[], l2=[])
@example(l1=[], l2=[1])
@run_in_pyodide
def test_array_extend(selenium_module_scope, l1, l2):
    from pyodide.ffi import to_js

    l1js1 = to_js(l1)
    l1js1.extend(l2)

    l1js2 = to_js(l1)
    l1js2 += l2

    l1.extend(l2)

    assert l1 == l1js1.to_py()
    assert l1 == l1js2.to_py()


@run_in_pyodide
def test_typed_array(selenium):
    from pyodide.code import run_js

    a = run_js("self.a = new Uint8Array([1,2,3,4]); a")
    assert a[0] == 1
    assert a[-1] == 4
    a[-2] = 7
    assert run_js("self.a[2]") == 7

    import pytest

    with pytest.raises(ValueError, match="cannot delete array elements"):
        del a[0]

    msg = "Slice subscripting isn't implemented for typed arrays"
    with pytest.raises(NotImplementedError, match=msg):
        a[:]

    msg = "Slice assignment isn't implemented for typed arrays"
    with pytest.raises(NotImplementedError, match=msg):
        a[:] = [-1, -2, -3, -4]

    assert not hasattr(a, "extend")
    with pytest.raises(TypeError):
        a += [1, 2, 3]


@pytest.mark.xfail_browsers(node="No document in node")
@run_in_pyodide
def test_html_array(selenium):
    from pyodide.code import run_js

    x = run_js("document.querySelectorAll('*')")
    assert run_js("(a, b) => a === b[0]")(x[0], x)
    assert run_js("(a, b) => a === Array.from(b).pop()")(x[-1], x)

    import pytest

    with pytest.raises(TypeError, match="does ?n[o']t support item assignment"):
        x[0] = 0

    with pytest.raises(TypeError, match="does ?n[o']t support item deletion"):
        del x[0]
