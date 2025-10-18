# See also test_pyproxy, test_jsproxy, and test_python.
import io
import pickle
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


class NoHypothesisUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Only allow safe classes from builtins.
        if module == "hypothesis":
            raise pickle.UnpicklingError()
        return super().find_class(module, name)


def no_hypothesis(x):
    try:
        NoHypothesisUnpickler(io.BytesIO(pickle.dumps(x))).load()
        return True
    except Exception:
        return False


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

    if isinstance(x_js, float):
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


@given(obj=any_equal_to_self_strategy.filter(no_hypothesis))
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


@given(obj=any_equal_to_self_strategy.filter(no_hypothesis))
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
@given(obj=any_strategy.filter(no_hypothesis))
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


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@given(obj=any_strategy.filter(no_hypothesis))
@example(obj=range(0, 2147483648))  # length is too big to fit in ssize_t
@settings(
    std_hypothesis_settings,
    max_examples=25,
)
@run_in_pyodide
def test_hypothesis(selenium_standalone, obj):
    from pyodide.ffi import to_js

    to_js(obj)


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

    assert list(
        run_js(
            """
                (x) => {
                    x = x.toJs();
                    return [x.constructor.name, x.length, x[0]];
                }
                """
        )(b"bytes")
    ) == ["Uint8Array", 5, 98]


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

    assert list(
        run_js(
            """
                (proxy) => {
                    let typename = proxy.type;
                    let x = proxy.toJs();
                    return [proxy.type, x.constructor.name, x[42]];
                }
                """
        )({42: 64})
    ) == ["dict", "Object", 64]


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
                if(x instanceof pyodide.ffi.PyProxy){
                    assert(() => !pyodide._api.pyproxyIsAlive(x));
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
                if(e instanceof pyodide.ffi.PyProxy){
                    assert(() => !pyodide._api.pyproxyIsAlive(e));
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


@run_in_pyodide
def test_js2python_null(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import jsnull

    assert run_js("null") is jsnull
    assert run_js("[null]")[0] is jsnull
    assert run_js("() => null")() is jsnull
    assert run_js("({a: null})").a is jsnull
    assert run_js("new Map([['a', null]])")["a"] is jsnull
    assert run_js("[null, null, null]").to_py() == [jsnull, jsnull, jsnull]
    assert run_js("new Map([['a', null]])").to_py() == {"a": jsnull}


@run_in_pyodide
def test_json_dumps_null(selenium):
    import json

    from pyodide.ffi import jsnull

    assert json.dumps(jsnull) == "null"
    assert (
        json.dumps([jsnull, jsnull, {jsnull: 1, 1: jsnull}])
        == '[null, null, {"null": 1, "1": null}]'
    )


@run_in_pyodide
def test_js2python_basic(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import jsnull

    t = run_js(
        """
        ({
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
        });
        """
    )
    assert t.jsstring_ucs1 == "pyodidé"
    assert t.jsstring_ucs2 == "碘化物"
    assert t.jsstring_ucs4 == "🐍"
    assert t.jsnumber0 == 42 and isinstance(t.jsnumber0, int)
    assert t.jsnumber1 == 42.5 and isinstance(t.jsnumber1, float)
    assert t.jsundefined is None
    assert t.jsnull is jsnull
    assert t.jstrue is True
    assert t.jsfalse is False
    assert t.jspython is open

    jsbytes = t.jsbytes.to_py()
    assert (jsbytes.tolist() == [1, 2, 3]) and (jsbytes.tobytes() == b"\x01\x02\x03")

    jsfloats = t.jsfloats.to_py()
    import struct

    expected = struct.pack("fff", 1, 2, 3)
    assert (jsfloats.tolist() == [1, 2, 3]) and (jsfloats.tobytes() == expected)
    assert str(t.jsobject) == "[object TextDecoder]"
    assert bool(t.jsobject) is True
    assert bool(t.jsarray0) is False
    assert bool(t.jsarray1) is True
    run_js("(t) => t.jspython.destroy()")(t)


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


@run_in_pyodide
def test_dict_subclass_to_js(selenium):
    """See issue #4636"""
    from collections import ChainMap

    from pyodide.code import run_js

    j = run_js(
        """
        (d) => JSON.stringify(d.toJs({ dict_converter: Object.fromEntries }))
        """
    )

    class D1(ChainMap, dict):  # type: ignore[misc, type-arg]
        pass

    class D2(dict, ChainMap):  # type: ignore[misc, type-arg]
        pass

    d = {"a": "b"}
    assert eval(j(D1({"a": "b"}))) == d
    assert eval(j(D2({"a": "b"}))) == d


def test_list_js2py2js(selenium):
    selenium.run_js("self.x = [1,2,3];")
    assert_js_to_py_to_js(selenium, "x")


def test_dict_js2py2js(selenium):
    selenium.run_js("self.x = { a : 1, b : 2, 0 : 3 };")
    assert_js_to_py_to_js(selenium, "x")


def test_error_js2py2js(selenium):
    selenium.run_js("self.err = new Error('hello there?');")
    assert_js_to_py_to_js(selenium, "err")
    if selenium.browser == "node":
        return
    selenium.run_js("self.err = new DOMException('hello there?');")
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
        point.z  # noqa: B018

    del point.y
    with pytest.raises(AttributeError, match="y"):
        point.y  # noqa: B018

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
        const x = pyodide.runPython(`
            class Test: pass
            [Test(), [Test(), [Test(), [Test()]]]]
        `);
        const Module = pyodide._module;
        const proxies = [];
        const result = Module._python2js_with_depth(Module.PyProxy_getPtr(x), -1, proxies);
        assert(() => proxies.length === 4);
        const result_proxies = [result[0], result[1][0], result[1][1][0], result[1][1][1][0]];
        const sortFunc = (x, y) => Module.PyProxy_getPtr(x) < Module.PyProxy_getPtr(y);
        proxies.sort(sortFunc);
        result_proxies.sort(sortFunc);
        for(let i = 0; i < 4; i++){
            assert(() => proxies[i] == result_proxies[i]);
        }
        x.destroy();
        for(const px of proxies){
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

    o = [(1, 2), (3, 4), [5, 6], {"a": 1, 2: 3, 4: 9}]

    assert run_js("(o) => Array.isArray(o.toJs())")(o)
    serialized = run_js("(o) => JSON.stringify(o.toJs())")(o)
    assert json.loads(serialized) == [[1, 2], [3, 4], [5, 6], {"a": 1, "2": 3, "4": 9}]
    serialized = run_js(
        "(o) => JSON.stringify(Array.from(Object.entries(o.toJs()[3])))"
    )(o)
    assert sorted(json.loads(serialized)) == [["2", 3], ["4", 9], ["a", 1]]


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
            assert(() => x instanceof pyodide.ffi.PyProxy, `i: ${i}, j: ${i}`);
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
            assert(() => x instanceof pyodide.ffi.PyProxy, `i: ${i}, j: ${i}`);
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
        let total_refs = pyodide._module._hiwire_num_refs();
        let res = respy.toJs();
        let new_total_refs = pyodide._module._hiwire_num_refs();
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
        let total_refs = pyodide._module._hiwire_num_refs();
        let res = respy.toJs();
        let new_total_refs = pyodide._module._hiwire_num_refs();
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


@run_in_pyodide
def test_tojs9(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import ConversionError, to_js

    result1 = to_js({1, "1"})
    assert set(run_js("(x) => Array.from(x.values())")(result1)) == {1, "1"}

    msg = "Key collision when converting Python dictionary to JavaScript. Key: '1'"
    with pytest.raises(ConversionError, match=msg):
        to_js({1: 7, "1": 9})


def test_tojs_literalmap(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        let pyodide = await loadPyodide({toJsLiteralMap: true});
        const res = pyodide.runPython(`
            from pyodide.ffi import to_js

            res = to_js({"a": 6, "b": 10, 6: 9, "get": 77, True: 90})
            res
        `);
        assert(() => res.constructor.name === "LiteralMap");
        assert(() => "a" in res);
        assert(() => "b" in res);
        assert(() => !(6 in res));
        assert(() => "get" in res);
        assert(() => !(true in res));
        assert(() => res.has("a"));
        assert(() => res.has("b"));
        assert(() => res.has(6));
        assert(() => res.has("get"));
        assert(() => res.has(true));
        assert(() => res.a === 6);
        assert(() => res.b === 10);
        assert(() => res[6] === undefined);
        assert(() => typeof res.get === "function");
        assert(() => res[true] === undefined);
        assert(() => res.get("a") === 6);
        assert(() => res.get("b") === 10);
        assert(() => res.get(6) === 9);
        assert(() => res.get("get") === 77);
        assert(() => res.get(true) === 90);
        res.delete("a");
        assert(() => !("a" in res));
        assert(() => !res.has("a"));
        res.a = 7;
        assert(() => res.a === 7);
        assert(() => res.get("a") === 7);
        res.set("a", 99);
        assert(() => res.get("a") === 99);
        assert(() => res.a === 99);
        delete res.a
        assert(() => !("a" in res));
        assert(() => !res.has("a"));
        """
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
    assert repr(type(a.to_py())) == "<class 'pyodide.ffi.JsProxy'>"


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

    with pytest.raises((ConversionError, JsException), match=msg):
        a = run_js(f"pyodide.toPy(new {obj})")


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


@run_in_pyodide
def test_to_js_eager_converter(selenium):
    import pytest

    from js import Array
    from pyodide.ffi import ConversionError, destroy_proxies, to_js

    recursive_list: Any = []
    recursive_list.append(recursive_list)

    recursive_dict: Any = {}
    recursive_dict[0] = recursive_dict

    a_thing = [{1: 2}, (2, 4, 6)]

    def normal(value, convert, cacheConversion):
        return convert(value)

    def reject_tuples(value, convert, cacheConversion):
        if isinstance(value, tuple):
            raise ConversionError("We don't convert tuples!")
        return convert(value)

    def proxy_tuples(value, convert, cacheConversion):
        if isinstance(value, tuple):
            return value
        return convert(value)

    to_js(recursive_list, eager_converter=normal)
    to_js(recursive_dict, eager_converter=normal)
    to_js(a_thing, eager_converter=normal)

    to_js(recursive_list, eager_converter=reject_tuples)
    to_js(recursive_dict, eager_converter=reject_tuples)
    with pytest.raises(ConversionError, match="We don't convert tuples"):
        to_js(a_thing, eager_converter=reject_tuples)

    to_js(recursive_list, eager_converter=proxy_tuples)
    to_js(recursive_dict, eager_converter=proxy_tuples)
    proxylist = Array.new()
    res = to_js(a_thing, eager_converter=proxy_tuples, pyproxies=proxylist)
    assert res[-1] == (2, 4, 6)
    assert len(proxylist) == 1
    destroy_proxies(proxylist)


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


def test_dict_converter_cache1(selenium):
    selenium.run_js(
        """
        let d1 = pyodide.runPython('d={0: {1: 2}}; d[1]=d[0]; d');
        let d = d1.toJs({dict_converter: Object.fromEntries});
        d1.destroy();
        assert(() => d[0] === d[1]);
        """
    )


@pytest.mark.xfail(reason="TODO: Fix me")
def test_dict_converter_cache2(selenium):
    selenium.run_js(
        """
        let d1 = pyodide.runPython('d={0: {1: 2}}; d[1]=d[0]; d[2] = d; d');
        let d = d1.toJs({dict_converter: Object.fromEntries});
        assert(() => d[2] === d);
        """
    )


@run_in_pyodide
def test_dict_and_default_converter(selenium):
    from js import Object
    from pyodide.ffi import to_js

    def default_converter(_obj, c, _):
        return c({"a": 2})

    class A:
        pass

    res = to_js(
        A, dict_converter=Object.fromEntries, default_converter=default_converter
    )
    assert res.a == 2


@run_in_pyodide
def test_bind_attrs(selenium):
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    class A(BindClass):
        x: int
        y: Annotated[list[int], Deep]

    a_px: JsProxy = run_js(
        """
        ({
            x: 7,
            y: [1,2,3],
        })
        """
    )
    a = a_px.bind_sig(A)
    assert a.x == 7
    assert a.y == [1, 2, 3]


@run_in_pyodide
def test_bind_call_convert(selenium):
    from typing import Annotated

    from _pyodide.jsbind import Deep, Json
    from pyodide.code import run_js

    def fsig(
        a: dict[str, int],
        b: Annotated[dict[str, int], Json],
        c: Annotated[dict[str, int], Deep],
        /,
    ) -> Annotated[list[int], Deep]:
        raise NotImplementedError

    f = run_js(
        """
        (function f(x, y, z) {
            return [x.get("a"), y.b, z.c]
        })
        """
    ).bind_sig(fsig)

    x = {"a": 2}
    y = {"b": 4}
    z = {"c": 6}
    assert f(x, y, z) == [2, 4, 6]


@run_in_pyodide
def test_bind_call_bind_return_value(selenium):
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js

    class A(BindClass):
        x: Annotated[list[int], Deep]

    def fsig() -> A:
        raise NotImplementedError

    f = run_js(
        """
        (function f() {
            return {x: [77, 1]};
        })
        """
    ).bind_sig(fsig)

    assert f().x == [77, 1]


@run_in_pyodide
async def test_bind_future_convert_result(selenium):
    from asyncio import Future
    from typing import Annotated

    from _pyodide.jsbind import Deep
    from pyodide.code import run_js

    def f1() -> Future[Annotated[list[int], Deep]]:
        raise NotImplementedError

    async def f2() -> Annotated[list[int], Deep]:
        raise NotImplementedError

    jsfunc = run_js(
        """
        (async function() {
            return [1,2,3];
        })
        """
    )
    f1 = jsfunc.bind_sig(f1)
    f2 = jsfunc.bind_sig(f2)
    assert await f1() == [1, 2, 3]
    assert await f2() == [1, 2, 3]


@run_in_pyodide
async def test_bind_future_bind_result(selenium):
    from asyncio import Future
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js

    class A(BindClass):
        x: Annotated[list[int], Deep]

    def f1() -> Future[A]:
        raise NotImplementedError

    async def f2() -> A:
        raise NotImplementedError

    jsfunc = run_js(
        """
        async function f() {
            return {x: [77, 1]};
        };
        f
        """
    )
    f1 = jsfunc.bind_sig(f1)
    f2 = jsfunc.bind_sig(f2)
    assert (await f1()).x == [77, 1]
    assert (await f2()).x == [77, 1]


@run_in_pyodide
def test_bind3(selenium):
    from pyodide.code import run_js

    o = run_js(
        """
        ({
            f(x, y, z) {
                return [x.get("a"), y.b, z.c]
            },
            x: [1,2,3],
            y: {
                g(x) {
                    return x.a;
                },
                c: [1,2,3]
            }
        })
        """
    )
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep, Json

    class B(BindClass):
        @staticmethod
        def g(x: Annotated[dict[str, int], Json], /) -> int:
            raise NotImplementedError

        c: Annotated[list[int], Deep]

    class A(BindClass):
        @staticmethod
        def f(
            a: dict[str, int],
            b: Annotated[dict[str, int], Json],
            c: Annotated[dict[str, int], Deep],
            /,
        ) -> Annotated[list[int], Deep]:
            raise NotImplementedError

        x: Annotated[list[int], Deep]
        y: B

    o2: A = o.bind_sig(A)
    f1 = o2.f
    f2 = o.f.bind_sig(A.f)

    x = {"a": 2}
    y = {"b": 4}
    z = {"c": 6}
    assert o2.f(x, y, z) == [2, 4, 6]
    assert f1(x, y, z) == [2, 4, 6]
    assert f2(x, y, z) == [2, 4, 6]
    assert o2.y.g({"a": 7}) == 7


@run_in_pyodide
async def test_bind_async1(selenium):
    from asyncio import Future
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js

    class A(BindClass):
        x: Future[Annotated[list[int], Deep]]

    a: A = run_js(
        """
        ({
            x: (async function () {
                return [1, 2, 3]
            })()
        })
        """
    ).bind_sig(A)

    assert await a.x == [1, 2, 3]


@run_in_pyodide
async def test_bind_async2(selenium):
    from asyncio import Future
    from typing import Annotated

    from _pyodide.jsbind import Deep
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    jsfunc: JsProxy = run_js(
        """
        (async function () {
            return [1, 2, 3]
        });
        """
    )

    async def f1() -> Annotated[list[int], Deep]:
        raise NotImplementedError

    def f2() -> Future[Annotated[list[int], Deep]]:
        raise NotImplementedError

    f1 = jsfunc.bind_sig(f1)
    f2 = jsfunc.bind_sig(f2)

    assert await f1() == [1, 2, 3]
    assert await f2() == [1, 2, 3]


@run_in_pyodide
async def test_bind_async3(selenium):
    from asyncio import Future
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    class A(BindClass):
        x: Annotated[list[int], Deep]

    async def f1() -> A:
        raise NotImplementedError

    def f2() -> Future[A]:
        raise NotImplementedError

    jsfunc: JsProxy = run_js(
        """
        (async function() {
            return {
                x : [1,2,3]
            };
        })
        """
    )

    f1 = jsfunc.bind_sig(f1)
    f2 = jsfunc.bind_sig(f2)

    assert (await f1()).x == [1, 2, 3]
    assert (await f2()).x == [1, 2, 3]


@run_in_pyodide
def test_bind_pre_convert(selenium):
    from typing import Annotated, _caches  # type:ignore[attr-defined]

    from _pyodide.jsbind import Deep, Py2JsConverterMeta
    from js import Headers  # type:ignore[attr-defined]
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    ajs: JsProxy = run_js("(x) => [x.toString(), JSON.stringify(Array.from(x))]")

    class ToHeaders(metaclass=Py2JsConverterMeta):
        @staticmethod
        def pre_convert(value):
            return Headers.new(value.items())

    def a(
        x: Annotated[dict[str, str] | None, ToHeaders], /
    ) -> Annotated[list[str], Deep]:
        return []

    abound = ajs.bind_sig(a)
    assert abound({"x": "y"}) == ["[object Headers]", '[["x","y"]]']
    _caches[Annotated._getitem.__wrapped__].cache_clear()  # type:ignore[attr-defined]


@run_in_pyodide
def test_bind_construct(selenium):
    from typing import Annotated, Any, NotRequired, TypedDict

    from _pyodide.jsbind import Default, Json
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    class Inner(TypedDict):
        b: int
        c: NotRequired[str]

    class Outer(TypedDict):
        a: list[Inner]
        x: int

    ajs: JsProxy = run_js("(x) => x")

    def a_shape(x: Annotated[Any, Default], /) -> Annotated[Outer, Json]:
        raise NotImplementedError

    # pyright infers abound has same type as a_shape,
    a = ajs.bind_sig(a_shape)
    o = run_js("({x: 7, a : [{b: 1, c: 'xyz'},{b: 2},{b: 3}]})")

    res = a(o)
    assert res["x"] == 7
    res["x"] = 9
    assert o.x == 9
    assert res["a"][0]["b"] == 1
    assert res["a"][0]["c"]
    assert "c" in res["a"][0]
    assert res["a"][0]["c"] == "xyz"
    assert res["a"][1]["b"] == 2
    assert "c" not in res["a"][1]
    res["a"][1]["c"] = "s"
    assert o.a[1].c == "s"


@run_in_pyodide
def test_bind_py_json(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    A: JsProxy = run_js("(class {x = 7})")

    class A_sig:
        x: int

    Abound = A.bind_class(A_sig)

    res = Abound()
    assert res.x == 7


@run_in_pyodide
def test_bind_class(selenium):
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    A_px: JsProxy = run_js("(class {x = [1,2,3]; f() { return [1]; }})")
    a_px: JsProxy = run_js("(A) => new A()")(A_px)

    class A_sig(BindClass):
        x: Annotated[list[int], Deep]

        def __init__(self, /): ...

        def f(self, /) -> Annotated[list[int], Deep]:
            return []

    A = A_px.bind_class(A_sig)
    res = A()
    assert isinstance(res.x, list)
    assert isinstance(res.f(), list)
    a = a_px.bind_sig(A_sig)
    assert isinstance(a.x, list)
    assert isinstance(a.f(), list)


@run_in_pyodide
def test_bind__call__(selenium):
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep, Json
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    class FuncType(BindClass):
        def __call__(
            self,
            a: dict[str, int],
            b: Annotated[dict[str, int], Json],
            c: Annotated[dict[str, int], Deep],
            /,
        ) -> Annotated[list[int], Deep]:
            return []

    f_px: JsProxy = run_js(
        """
        (function f(x, y, z) {
            return [x.get("a"), y.b, z.c]
        })
        """
    )
    f = f_px.bind_sig(FuncType)

    assert f({"a": 7}, {"b": 9}, {"c": 11}) == [7, 9, 11]


@run_in_pyodide
def test_bind_getattr(selenium):
    from typing import Annotated

    from _pyodide.jsbind import BindClass, Deep, Json
    from pyodide.code import run_js
    from pyodide.ffi import JsProxy

    class FuncType(BindClass):
        def __call__(
            self,
            a: dict[str, int],
            b: Annotated[dict[str, int], Json],
            c: Annotated[dict[str, int], Deep],
            /,
        ) -> Annotated[list[int], Deep]:
            return []

    class T:
        def __getattr__(self, name: str) -> FuncType:
            raise NotImplementedError

    t_px: JsProxy = run_js(
        """
        ({
            f(x, y, z) {
                return [x.get("a"), y.b, z.c]
            },
            g() {
                return [1, 2, 3];
            }
        })
        """
    )
    t = t_px.bind_sig(T)

    assert t.f({"a": 7}, {"b": 9}, {"c": 11}) == [7, 9, 11]
    assert t.g({"a": 7}, {"b": 9}, {"c": 11}) == [1, 2, 3]


@run_in_pyodide
def test_to_js_no_leak(selenium):
    from js import Object
    from pyodide.ffi import to_js

    d = {"key": Object()}
    to_js(d)


@run_in_pyodide
def test_js_callable_not_function(selenium):
    from pyodide.code import run_js

    o = run_js(
        """
        function nonFuncCallable (...params) {
            console.log(this);
            return [this, ...params]
        }
        Object.setPrototypeOf(nonFuncCallable, {})
        const o = {nonFuncCallable};
        o
        """
    )
    assert list(o.nonFuncCallable(1, 2, 3)) == [o, 1, 2, 3]
