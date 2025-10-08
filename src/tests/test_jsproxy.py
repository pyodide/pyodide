# See also test_typeconversions, and test_python.

from typing import no_type_check

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from pytest_pyodide import run_in_pyodide
from pytest_pyodide.hypothesis import std_hypothesis_settings


def test_jsproxy_dir(selenium):
    result = selenium.run_js(
        """
        self.a = { x : 2, y : "9" };
        self.b = function(){};
        let pyresult = pyodide.runPython(`
            from js import a
            from js import b
            [dir(a), dir(b)]
        `);
        let result = pyresult.toJs();
        pyresult.destroy();
        return result;
        """
    )
    jsproxy_items = {
        "__bool__",
        "__class__",
        "__defineGetter__",
        "__defineSetter__",
        "__delattr__",
        "constructor",
        "toString",
        "typeof",
        "valueOf",
    }
    a_items = {"x", "y"}
    callable_items = {"__call__", "new"}
    set0 = set(result[0])
    set1 = set(result[1])
    assert set0.issuperset(jsproxy_items)
    assert set0.isdisjoint(callable_items)
    assert set0.issuperset(a_items)
    assert set1.issuperset(jsproxy_items)
    assert set1.issuperset(callable_items)
    assert set1.isdisjoint(a_items)
    selenium.run_js(
        """
        self.a = [0,1,2,3,4,5,6,7,8,9];
        a[27] = 0;
        a[":"] = 0;
        a["/"] = 0;
        a.abcd = 0;
        a.α = 0;

        pyodide.runPython(`
            from js import a
            d = dir(a)
            assert '0' not in d
            assert '9' not in d
            assert '27' not in d
            assert ':' in d
            assert '/' in d
            assert 'abcd' in d
            assert 'α' in d
        `);
        """
    )


def test_jsproxy_getattr(selenium):
    assert selenium.run_js(
        """
            self.a = { x : 2, y : "9", typeof : 7 };
            let pyresult = pyodide.runPython(`
                from js import a
                [ a.x, a.y, a.typeof ]
            `);
            let result = pyresult.toJs();
            pyresult.destroy();
            return result;
            """
    ) == [2, "9", "object"]


@run_in_pyodide
def test_jsproxy_getattr_errors(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException

    o = run_js("({get a() { throw new Error('oops'); } })")
    with pytest.raises(AttributeError):
        o.x  # noqa: B018
    with pytest.raises(JsException):
        o.a  # noqa: B018


@pytest.mark.xfail_browsers(node="No document in node")
@run_in_pyodide
def test_jsproxy_document(selenium):
    from js import document

    el = document.createElement("div")
    assert el.tagName == "DIV"
    assert bool(el)
    assert not document.body.children
    document.body.appendChild(el)
    assert document.body.children
    assert len(document.body.children) == 1
    assert document.body.children[0] == el
    assert repr(document) == "[object HTMLDocument]"
    assert len(dir(el)) >= 200
    assert "appendChild" in dir(el)


@pytest.mark.parametrize(
    "js,result",
    [
        ("{}", True),
        ("{a:1}", True),
        ("[]", False),
        ("[1]", True),
        ("new Map()", False),
        ("new Map([[0, 0]])", True),
        ("new Set()", False),
        ("new Set([0])", True),
        ("class T {}", True),
        ("new (class T {})", True),
        ("new Uint8Array(0)", False),
        ("new Uint8Array(1)", True),
        ("new ArrayBuffer(0)", False),
        ("new ArrayBuffer(1)", True),
    ],
)
@run_in_pyodide
def test_jsproxy_bool(selenium, js, result):
    from pyodide.code import run_js

    assert bool(run_js(f"({js})")) == result


@pytest.mark.xfail_browsers(node="No document in node")
@pytest.mark.parametrize(
    "js,result",
    [
        ("document.createElement('div')", True),
        ("document.createElement('select')", True),
        ("document.createElement('p')", True),
        ("document.createElement('style')", True),
        ("document.createElement('ul')", True),
        ("document.createElement('ul').style", True),
        ("document.querySelectorAll('x')", False),
        ("document.querySelectorAll('body')", True),
        ("document.all", False),
    ],
)
@run_in_pyodide
def test_jsproxy_bool_html(selenium, js, result):
    from pyodide.code import run_js

    assert bool(run_js(js)) == result


@pytest.mark.xfail_browsers(node="No ImageData in node")
@run_in_pyodide
def test_jsproxy_imagedata(selenium):
    from js import ImageData

    assert ImageData.new(64, 64).width == 64
    assert ImageData.typeof == "function"


def test_jsproxy_function(selenium):
    selenium.run_js("self.square = function (x) { return x*x; };")
    assert (
        selenium.run(
            """
            from js import square
            square(2)
            """
        )
        == 4
    )


def test_jsproxy_class(selenium):
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        self.TEST = new Point(42, 43);
        """
    )
    assert (
        selenium.run(
            """
            from js import TEST
            del TEST.y
            hasattr(TEST, 'y')
            """
        )
        is False
    )


@run_in_pyodide
def test_jsproxy_map(selenium):
    import pytest

    from pyodide.code import run_js

    TEST = run_js('new Map([["x", 42], ["y", 43]])')
    assert "y" in TEST
    del TEST["y"]
    assert "y" not in TEST

    with pytest.raises(KeyError):
        del TEST["y"]

    assert TEST == TEST  # noqa: PLR0124
    assert TEST != "foo"

    TEST = run_js("({foo: 'bar', baz: 'bap'})")
    assert dict(TEST.object_entries()) == {"foo": "bar", "baz": "bap"}


def test_jsproxy_iter(selenium):
    selenium.run_js(
        """
        function makeIterator(array) {
          let nextIndex = 0;
          return {
            next: function() {
              return nextIndex < array.length ?
                {value: array[nextIndex++], done: false} :
                {done: true};
            }
          };
        }
        self.ITER = makeIterator([1, 2, 3]);"""
    )
    selenium.run("from js import ITER")
    assert selenium.run("list(ITER)") == [1, 2, 3]


def test_jsproxy_implicit_iter(selenium):
    selenium.run_js(
        """
        self.ITER = [1, 2, 3];
        """
    )
    selenium.run("from js import ITER, Object")
    assert selenium.run("list(ITER)") == [1, 2, 3]
    assert selenium.run("list(ITER.values())") == [1, 2, 3]
    assert selenium.run("list(Object.values(ITER))") == [1, 2, 3]


def test_jsproxy_call1(selenium):
    assert selenium.run_js(
        """
            self.f = function(){ return arguments.length; };
            let pyresult = pyodide.runPython(
                `
                from js import f
                [f(*range(n)) for n in range(10)]
                `
            );
            let result = pyresult.toJs();
            pyresult.destroy();
            return result;
            """
    ) == list(range(10))


@run_in_pyodide
def test_jsproxy_call2(selenium):
    from pyodide.code import run_js

    f = run_js("(function(){ return arguments.length; })")
    assert [f(*range(n)) for n in range(10)] == list(range(10))


def test_jsproxy_call_kwargs(selenium):
    assert selenium.run_js(
        """
            self.kwarg_function = ({ a = 1, b = 1 }) => {
                return [a, b];
            };
            return pyodide.runPython(
                `
                from js import kwarg_function
                kwarg_function(b = 2, a = 10)
                `
            );
            """
    ) == [10, 2]


@pytest.mark.xfail
def test_jsproxy_call_meth_py(selenium):
    assert selenium.run_js(
        """
        self.a = {};
        return pyodide.runPython(
            `
            from js import a
            def f(self):
                return self
            a.f = f
            a.f() == a
            `
        );
        """
    )


def test_jsproxy_call_meth_js(selenium):
    assert selenium.run_js(
        """
        self.a = {};
        function f(){return this;}
        a.f = f;
        return pyodide.runPython(
            `
            from js import a
            a.f() == a
            `
        );
        """
    )


def test_jsproxy_call_meth_js_kwargs(selenium):
    assert selenium.run_js(
        """
        self.a = {};
        function f({ x = 1, y = 1 }){
            return [this, x, y];
        }
        a.f = f;
        return pyodide.runPython(
            `
            from js import a
            [r0, r1, r2] = a.f(y=10, x=2)
            r0 == a and r1 == 2 and r2 == 10
            `
        );
        """
    )


def test_call_pyproxy_destroy_args(selenium):
    selenium.run_js(
        r"""
        let y;
        pyodide.setDebug(true);
        self.f = function(x){ y = x; }
        pyodide.runPython(`
            from js import f
            f({})
            f([])
        `);
        assertThrows(() => y.length, "Error",
            "This borrowed proxy was automatically destroyed at the end of a function call.*\n" +
            'The object was of type "list" and had repr "\\[\\]"'
        );
        """
    )

    selenium.run_js(
        r"""
        let y;
        pyodide.setDebug(false);
        self.f = function(x){ y = x; }
        pyodide.runPython(`
            from js import f
            f({})
            f([])
        `);
        assertThrows(() => y.length, "Error",
            "This borrowed proxy was automatically destroyed at the end of a function call.*\n" +
            'For more information about the cause of this error, use `pyodide.setDebug.true.`'
        );
        """
    )

    selenium.run_js(
        """
        let y;
        self.f = async function(x){
            await sleep(5);
            y = x;
        }
        await pyodide.runPythonAsync(`
            from js import f
            await f({})
            await f([])
        `);
        assertThrows(() => y.length, "Error", "This borrowed proxy was automatically destroyed");
        """
    )


def test_call_pyproxy_set_global(selenium):
    selenium.run_js(
        """
        self.setGlobal = function(x){
            if(self.myGlobal instanceof pyodide.ffi.PyProxy){
                self.myGlobal.destroy();
            }
            if(x instanceof pyodide.ffi.PyProxy){
                x = x.copy();
            }
            self.myGlobal = x;
        }
        pyodide.runPython(`
            from js import setGlobal
            setGlobal(2)
            setGlobal({})
            setGlobal([])
            setGlobal(3)
        `);
        """
    )

    selenium.run_js(
        """
        self.setGlobal = async function(x){
            await sleep(5);
            if(self.myGlobal instanceof pyodide.ffi.PyProxy){
                self.myGlobal.destroy();
            }
            if(x instanceof pyodide.ffi.PyProxy){
                x = x.copy();
            }
            self.myGlobal = x;
        }
        await pyodide.runPythonAsync(`
            from js import setGlobal
            await setGlobal(2)
            await setGlobal({})
            await setGlobal([])
            await setGlobal(3)
        `);
        """
    )


def test_call_pyproxy_destroy_result(selenium):
    selenium.run_js(
        """
        self.f = function(){
            let dict = pyodide.globals.get("dict");
            let result = dict();
            dict.destroy();
            return result;
        }
        pyodide.runPython(`
            from js import f
            import sys
            d = f()
            assert sys.getrefcount(d) == 2
        `);
        """
    )

    selenium.run_js(
        """
        self.f = async function(){
            await sleep(5);
            let dict = pyodide.globals.get("dict");
            let result = dict();
            dict.destroy();
            return result;
        }
        await pyodide.runPythonAsync(`
            from js import f
            import sys
            d = await f()
        `);
        pyodide.runPython(`
            assert sys.getrefcount(d) == 2
        `);
        """
    )


@pytest.mark.skip_refcount_check
def test_call_pyproxy_return_arg(selenium):
    selenium.run_js(
        """
        self.f = function f(x){
            return x;
        }
        pyodide.runPython(`
            from js import f
            l = [1,2,3]
            x = f(l)
            assert x is l
            import sys
            assert sys.getrefcount(x) == 3
        `);
        """
    )
    selenium.run_js(
        """
        self.f = async function f(x){
            await sleep(5);
            return x;
        }
        await pyodide.runPythonAsync(`
            from js import f
            l = [1,2,3]
            x = await f(l)
            assert x is l
        `);
        pyodide.runPython(`
            import sys
            assert sys.getrefcount(x) == 3
        `);
        """
    )


@run_in_pyodide
def test_import_invocation(selenium):
    import js

    def temp():
        print("okay?")

    from pyodide.ffi import create_once_callable

    js.setTimeout(create_once_callable(temp), 100)
    js.fetch("pyodide-lock.json")


@run_in_pyodide
def test_import_bind(selenium):
    from js import fetch

    fetch("pyodide-lock.json")


@run_in_pyodide
def test_nested_attribute_access(selenium):
    import js
    from js import self

    assert js.Float64Array.BYTES_PER_ELEMENT == 8
    assert self.Float64Array.BYTES_PER_ELEMENT == 8


def test_destroy_attribute(selenium):
    selenium.run_js(
        """
        let test = pyodide.runPython(`
            class Test:
                a = {}
            test = Test()
            test
        `);
        pyodide.runPython(`
            import sys
            assert sys.getrefcount(test) == 3
            assert sys.getrefcount(test.a) == 2
        `);
        test.a;
        pyodide.runPython(`
            assert sys.getrefcount(test) == 3
            assert sys.getrefcount(test.a) == 3
        `);
        test.a.destroy();
        pyodide.runPython(`
            assert sys.getrefcount(test) == 3
            assert sys.getrefcount(test.a) == 2
        `);
        test.a;
        pyodide.runPython(`
            assert sys.getrefcount(test) == 3
            assert sys.getrefcount(test.a) == 3
        `);
        test.destroy();
        pyodide.runPython(`
            assert sys.getrefcount(test) == 2
            assert sys.getrefcount(test.a) == 2
        `);
        """
    )


@run_in_pyodide
def test_window_isnt_super_weird_anymore(selenium):
    import js
    from js import Array, self

    assert self.Array != self
    assert self.Array == Array
    assert self.self.self.self == self
    assert js.self.Array == Array
    assert js.self.self.self.self == self
    assert self.self.self.self.Array == Array


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_mount_object(selenium_standalone):
    selenium = selenium_standalone
    result = selenium.run_js(
        """
        function x1(){
            return "x1";
        }
        function x2(){
            return "x2";
        }
        function y(){
            return "y";
        }
        let a = { x : x1, y, s : 3, t : 7};
        let b = { x : x2, y, u : 3, t : 7};
        pyodide.registerJsModule("a", a);
        pyodide.registerJsModule("b", b);
        let result_proxy = pyodide.runPython(`
            from a import x
            from b import x as x2
            result = [x(), x2()]
            import a
            import b
            result += [a.s, dir(a), dir(b)]
            result
        `);
        let result = result_proxy.toJs()
        result_proxy.destroy();
        return result;
        """
    )
    assert result[:3] == ["x1", "x2", 3]
    assert {x for x in result[3] if len(x) == 1} == {"x", "y", "s", "t"}
    assert {x for x in result[4] if len(x) == 1} == {"x", "y", "u", "t"}
    selenium.run_js(
        """
        pyodide.unregisterJsModule("a");
        pyodide.unregisterJsModule("b");
        """
    )
    selenium.run(
        """
        import sys
        del sys.modules["a"]
        del sys.modules["b"]
        """
    )


def test_unregister_jsmodule(selenium):
    selenium.run_js(
        """
        let a = new Map(Object.entries({ s : 7 }));
        let b = new Map(Object.entries({ t : 3 }));
        pyodide.registerJsModule("a", a);
        pyodide.registerJsModule("a", b);
        pyodide.unregisterJsModule("a");
        await pyodide.runPythonAsync(`
            from unittest import TestCase
            raises = TestCase().assertRaises
            with raises(ImportError):
                import a
        `);
        """
    )


def test_unregister_jsmodule_error(selenium):
    selenium.run_js(
        """
        try {
            pyodide.unregisterJsModule("doesnotexist");
            throw new Error("unregisterJsModule should have thrown an error.");
        } catch(e){
            if(!e.message.includes("Cannot unregister 'doesnotexist': no Javascript module with that name is registered")){
                throw e;
            }
        }
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide
def test_jsmod_import_star1(selenium):
    import sys
    from typing import Any

    from pyodide.code import run_js

    run_js("pyodide.registerJsModule('xx', {a: 2, b: 7, f(x){ return x + 1; }});")
    g: dict[str, Any] = {}
    exec("from xx import *", g)
    try:
        assert "a" in g
        assert "b" in g
        assert "f" in g
        assert "__all__" not in g
        assert g["a"] == 2
        assert g["b"] == 7
        assert g["f"](9) == 10
    finally:
        sys.modules.pop("xx", None)
        run_js("pyodide.unregisterJsModule('xx');")


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide
def test_jsmod_import_star2(selenium):
    import sys
    from typing import Any

    from pyodide.code import run_js

    run_js(
        "pyodide.registerJsModule('xx', {a: 2, b: 7, f(x){ return x + 1; }, __all__ : pyodide.toPy(['a'])});"
    )
    g: dict[str, Any] = {}
    exec("from xx import *", g)
    try:
        assert "a" in g
        assert "b" not in g
        assert "f" not in g
        assert "__all__" not in g
        assert g["a"] == 2
    finally:
        sys.modules.pop("xx", None)
        run_js("pyodide.unregisterJsModule('xx');")


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_nested_import(selenium_standalone):
    selenium = selenium_standalone
    assert (
        selenium.run_js(
            """
            self.a = { b : { c : { d : 2 } } };
            return pyodide.runPython("from js.a.b import c; c.d");
            """
        )
        == 2
    )
    selenium.run(
        """
        import sys
        del sys.modules["js.a"]
        del sys.modules["js.a.b"]
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_register_jsmodule_docs_example(selenium_standalone):
    selenium = selenium_standalone
    selenium.run_js(
        """
        let my_module = {
        f : function(x){
            return x*x + 1;
        },
        g : function(x){
            console.log(`Calling g on argument ${x}`);
            return x;
        },
        submodule : {
            h : function(x) {
            return x*x - 1;
            },
            c  : 2,
        },
        };
        pyodide.registerJsModule("my_js_module", my_module);
        """
    )
    selenium.run(
        """
        import my_js_module
        from my_js_module.submodule import h, c
        assert my_js_module.f(7) == 50
        assert h(9) == 80
        assert c == 2
        import sys
        del sys.modules["my_js_module"]
        del sys.modules["my_js_module.submodule"]
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_register_non_extendable_jsmodule(selenium_standalone):
    selenium_standalone.run_js(
        """
        pyodide.registerJsModule("x", Object.preventExtensions({aaa: 2, bbb: 7}))
        """
    )

    @run_in_pyodide
    def check_import_star(selenium):
        a = {}  # type:ignore[var-annotated]
        exec("from x import *", a)
        assert set(a).issuperset({"aaa", "bbb"})

    check_import_star(selenium_standalone)


@run_in_pyodide
def test_object_entries_keys_values(selenium):
    from pyodide.code import run_js

    x = run_js("({ a : 2, b : 3, c : 4 })")
    assert x.object_entries().to_py() == [["a", 2], ["b", 3], ["c", 4]]
    assert x.object_keys().to_py() == ["a", "b", "c"]
    assert x.object_values().to_py() == [2, 3, 4]


def test_mixins_feature_presence(selenium):
    selenium.run_js(
        """
        let fields = [
            [{ [Symbol.iterator](){} }, "__iter__"],
            [{ next(){} }, "__next__", "__iter__"],
            [{ length : 1 }, "__len__"],
            [{ get(){} }, "__getitem__"],
            [{ set(){} }, "__setitem__", "__delitem__"],
            [{ has(){} }, "__contains__"],
            [{ then(){} }, "__await__"]
        ];

        let test_object = pyodide.runPython(`
            from js import console
            def test_object(obj, keys_expected):
                for [key, expected_val] in keys_expected.object_entries():
                    actual_val = hasattr(obj, key)
                    if actual_val != expected_val:
                        console.log(obj)
                        console.log(key)
                        console.log(actual_val)
                        assert False
            test_object
        `);

        for(let flags = 0; flags < (1 << fields.length); flags ++){
            let o = {};
            let keys_expected = {};
            for(let [idx, [obj, ...keys]] of fields.entries()){
                if(flags & (1<<idx)){
                    Object.assign(o, obj);
                }
                for(let key of keys){
                    keys_expected[key] = keys_expected[key] || !!(flags & (1<<idx));
                }
            }
            test_object(o, keys_expected);
        }
        test_object.destroy();
        """
    )


def test_mixins_calls(selenium):
    result = selenium.run_js(
        """
        self.testObjects = {};
        testObjects.iterable = { *[Symbol.iterator](){
            yield 3; yield 5; yield 7;
        } };
        testObjects.iterator = testObjects.iterable[Symbol.iterator]();
        testObjects.has_len1 = { length : 7, size : 10 };
        testObjects.has_len2 = { length : 7 };
        testObjects.has_get = { get(x){ return x; } };
        testObjects.has_getset = new Map();
        testObjects.has_has = { has(x){ return typeof(x) === "string" && x.startsWith("x") } };
        testObjects.has_includes = { includes(x){ return typeof(x) === "string" && x.startsWith("a") } };
        testObjects.has_has_includes = {
            includes(x){ return typeof(x) === "string" && x.startsWith("a") },
            has(x){ return typeof(x) === "string" && x.startsWith("x") }
        };
        testObjects.awaitable = { then(cb){ cb(7); } };

        let pyresult = await pyodide.runPythonAsync(`
            from js import testObjects as obj
            result = []
            result.append(["iterable1", list(iter(obj.iterable)), [3, 5, 7]])
            result.append(["iterable2", [*obj.iterable], [3, 5, 7]])
            it = obj.iterator
            result.append(["iterator", [next(it), next(it), next(it)], [3, 5, 7]])
            result.append(["has_len1", len(obj.has_len1), 10])
            result.append(["has_len2", len(obj.has_len2), 7])
            result.append(["has_get1", obj.has_get[10], 10])
            result.append(["has_get2", obj.has_get[11], 11])
            m = obj.has_getset
            m[1] = 6
            m[2] = 77
            m[3] = 9
            m[2] = 5
            del m[3]
            result.append(["has_getset", [x.to_py() for x in m.entries()], [[1, 6], [2, 5]]])
            result.append(["has_has", [n in obj.has_has for n in ["x9", "a9"]], [True, False]])
            result.append(["has_includes", [n in obj.has_includes for n in ["x9", "a9"]], [False, True]])
            result.append(["has_has_includes", [n in obj.has_has_includes for n in ["x9", "a9"]], [True, False]])
            result.append(["awaitable", await obj.awaitable, 7])
            result
        `);
        let result = pyresult.toJs();
        pyresult.destroy();
        return result;
        """
    )
    for [desc, a, b] in result:
        assert a == b, desc


def test_mixins_errors_1(selenium):
    selenium.run_js(
        """
        self.a = [];
        self.b = {
            has(){ return false; },
            get(){ return undefined; },
            set(){ return false; },
            delete(){ return false; },
        };
        pyodide.runPython(`
            from unittest import TestCase
            raises = TestCase().assertRaises
            from js import a, b
            with raises(IndexError):
                a[0]
            with raises(IndexError):
                del a[0]
            with raises(KeyError):
                b[0]
            with raises(KeyError):
                del b[0]
        `);
        """
    )


def test_mixins_errors_2(selenium):
    selenium.run_js(
        """
        self.c = {
            next(){},
            length : 1,
            get(){},
            set(){},
            has(){},
            then(){}
        };
        self.d = {
            [Symbol.iterator](){},
        };
        pyodide.runPython("from js import c, d");
        delete c.next;
        delete c.length;
        delete c.get;
        delete c.set;
        delete c.has;
        delete c.then;
        delete d[Symbol.iterator];
        pyodide.runPython(`
            from contextlib import contextmanager
            from unittest import TestCase
            @contextmanager
            def raises(exc, match=None):
                with TestCase().assertRaisesRegex(exc, match) as e:
                    yield e

            from pyodide.ffi import JsException
            msg = "^TypeError:.* is not a function.*"
            with raises(JsException, match=msg):
                next(c)
            with raises(JsException, match=msg):
                iter(d)
            with raises(TypeError, match="object does not have a valid length"):
                len(c)
            with raises(JsException, match=msg):
                c[0]
            with raises(JsException, match=msg):
                c[0] = 7
            with raises(JsException, match=msg):
                del c[0]
        `)

        await pyodide.runPythonAsync(`
            with raises(TypeError, match="can't be used in 'await' expression"):
                await c
        `);
        """
    )


@run_in_pyodide
def test_mixins_errors_3(selenium):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises

    l = run_js(
        """
        const l = [0, false, NaN, undefined, null];
        l[6] = 7;
        l
        """
    )

    with raises(IndexError):
        l[10]
    with raises(IndexError):
        l[5]
    assert len(l) == 7
    l[0]
    l[1]
    l[2]
    l[3]
    l[4]
    l[6]
    del l[1]
    with raises(IndexError):
        l[4]
    l[5]
    del l[4]
    l[3]
    l[4]


@run_in_pyodide
def test_mixins_errors_4(selenium):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises

    m = run_js(
        """
        l = [0, false, NaN, undefined, null];
        l[6] = 7;
        let a = Array.from(self.l.entries());
        a.splice(5, 1);
        m = new Map(a);
        m
        """
    )

    with raises(KeyError):
        m[10]
    with raises(KeyError):
        m[5]
    assert len(m) == 6
    m[0]
    m[1]
    m[2]
    m[3]
    m[4]
    m[6]
    del m[1]
    with raises(KeyError):
        m[1]
    assert len(m) == 5


def test_buffer(selenium):
    selenium.run_js(
        """
        self.a = new Uint32Array(Array.from({length : 10}, (_,idx) => idx));
        pyodide.runPython(`
            from js import a
            b = a.to_py()
            b[4] = 7
            assert b[8] == 8
            a.assign_to(b)
            assert b[4] == 4
            b[4] = 7
            a.assign(b)
            assert a[4] == 7
        `);
        if(a[4] !== 7){
            throw Error();
        }
        """
    )
    selenium.run_js(
        """
        self.a = new Uint32Array(Array.from({length : 10}, (_,idx) => idx));
        pyodide.runPython(`
            import js
            from unittest import TestCase
            raises = TestCase().assertRaisesRegex
            from array import array
            from js import a
            c = array('b', range(30))
            d = array('b', range(40))
            with raises(ValueError, "cannot assign to TypedArray"):
                a.assign(c)

            with raises(ValueError, "cannot assign from TypedArray"):
                a.assign_to(c)

            with raises(ValueError, "incompatible formats"):
                a.assign(d)

            with raises(ValueError, "incompatible formats"):
                a.assign_to(d)

            e = array('I', range(10, 20))
            a.assign(e)
        `);
        for(let [k, v] of a.entries()){
            if(v !== k + 10){
                throw new Error([v, k]);
            }
        }
        """
    )


@run_in_pyodide
def test_buffer_to_file(selenium):
    from js import Uint8Array

    a = Uint8Array.new(range(10))
    from tempfile import TemporaryFile

    with TemporaryFile() as f:
        a.to_file(f)
        f.seek(0)
        assert f.read() == a.to_bytes()

        b = b"abcdef"
        f.write(b)
        f.seek(-len(b), 1)
        a.from_file(f)
        assert list(a.subarray(0, len(b)).to_bytes()) == list(b)


@run_in_pyodide
def test_buffer_into_file(selenium):
    from js import Uint8Array

    a = Uint8Array.new(range(10))
    from tempfile import TemporaryFile

    with TemporaryFile() as f:
        b = a.to_bytes()
        a._into_file(f)
        f.seek(0)
        assert f.read() == b


@run_in_pyodide
def test_buffer_into_file2(selenium):
    """Check that no copy occurred."""
    import pyodide_js
    from js import Uint8Array

    a = Uint8Array.new(range(10))
    from tempfile import TemporaryFile

    with TemporaryFile() as f:
        a._into_file(f)
        assert pyodide_js.FS.streams[f.fileno()].node.contents.buffer == a.buffer


def test_buffer_assign_back(selenium):
    result = selenium.run_js(
        """
        self.jsarray = new Uint8Array([1, 2, 3, 4, 5, 6]);
        pyodide.runPython(`
            from js import jsarray
            array = jsarray.to_py()
            array[1::2] = bytes([20, 77, 9])
            jsarray.assign(array)
        `);
        return Array.from(jsarray)
        """
    )
    assert result == [1, 20, 3, 77, 5, 9]


@run_in_pyodide
def test_buffer_conversions(selenium):
    from pyodide.code import run_js

    s, jsbytes = run_js(
        """
        const s = "abcဴ";
        const jsbytes = new TextEncoder().encode(s);
        [s, jsbytes]
        """
    )
    memoryview_conversion = jsbytes.to_memoryview()
    bytes_conversion = jsbytes.to_bytes()

    assert bytes_conversion.decode() == s
    assert bytes(memoryview_conversion) == bytes_conversion


@run_in_pyodide
def test_tostring_encoding(selenium):
    from pyodide.code import run_js

    bytes = run_js(
        """
        // windows-1251 encoded "Привет, мир!" which is Russian for "Hello, world!"
        new Uint8Array([207, 240, 232, 226, 229, 242, 44, 32, 236, 232, 240, 33]);
        """
    )

    assert bytes.to_string("windows-1251") == "Привет, мир!"


@run_in_pyodide
def test_tostring_error(selenium):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises

    bytes = run_js(
        """
        // windows-1251 encoded "Привет, мир!" which is Russian for "Hello, world!"
        new Uint8Array([207, 240, 232, 226, 229, 242, 44, 32, 236, 232, 240, 33]);
        """
    )

    with raises(ValueError):
        bytes.to_string()


@run_in_pyodide
def test_duck_buffer_method_presence(selenium):
    from pyodide.code import run_js

    bytes = run_js(
        "new Uint8Array([207, 240, 232, 226, 229, 242, 44, 32, 236, 232, 240, 33])"
    )
    other = run_js("{}")

    buffer_methods = {"assign", "assign_to", "to_string", "to_memoryview", "to_bytes"}
    assert buffer_methods < set(dir(bytes))
    assert not set(dir(other)).intersection(buffer_methods)


def test_memory_leaks(selenium):
    # refcounts are tested automatically in conftest by default
    selenium.run_js(
        """
        self.a = [1,2,3];
        pyodide.runPython(`
            from js import a
            repr(a)
            [*a]
            None
        `);
        """
    )


@run_in_pyodide
def test_raise_js_error(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException

    e = run_js("new Error('hi')")
    with pytest.raises(JsException):
        raise e


@run_in_pyodide
def test_js_id(selenium):
    from pyodide.code import run_js

    [x, y, z] = run_js("let a = {}; let b = {}; [a, a, b]")
    assert x.js_id == y.js_id
    assert x is not y
    assert x.js_id != z.js_id


@run_in_pyodide
def test_object_with_null_constructor(selenium):
    from pyodide.code import run_js

    o = run_js("Object.create(null)")
    assert repr(o) == "[object Object]"


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


@run_in_pyodide
def test_jsarray_reversed(selenium):
    from pyodide.code import run_js

    l = [5, 7, 9, -1, 3, 5]
    a = run_js(repr(l))
    b = run_js(f"new Int8Array({repr(l)})")
    it1 = reversed(l)
    it2 = reversed(a)
    it3 = reversed(b)

    for _ in range(len(l)):
        v = next(it1)
        assert next(it2) == v
        assert next(it3) == v

    import pytest

    with pytest.raises(StopIteration):
        next(it1)
    with pytest.raises(StopIteration):
        next(it2)
    with pytest.raises(StopIteration):
        next(it3)


@run_in_pyodide
def test_jsarray_reverse(selenium):
    from pyodide.code import run_js

    l = [5, 7, 9, 0, 3, 1]
    a = run_js(repr(l))
    b = run_js(f"new Int8Array({repr(l)})")

    l.reverse()
    a.reverse()
    b.reverse()

    assert a.to_py() == l
    assert b.to_bytes() == bytes(l)


@run_in_pyodide
def test_array_empty_slot(selenium):
    import pytest

    from pyodide.code import run_js

    a = run_js("[1,,2]")
    with pytest.raises(IndexError):
        a[1]

    assert a.to_py() == [1, None, 2]
    del a[1]
    assert a.to_py() == [1, 2]


@run_in_pyodide
def test_array_pop(selenium):
    from pyodide.code import run_js

    a = run_js("[1, 2, 3]")
    assert a.pop() == 3
    assert a.pop(0) == 1


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
        jsl[:] = 1  # type: ignore[call-overload]

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

    with pytest.raises(TypeError, match="object doesn't support item deletion"):
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


@pytest.mark.parametrize(
    "sequence_converter",
    [
        "(x) => x",
        "(x) => new Uint8Array(x)",
        "(x) => Object.create({[Symbol.toStringTag] : 'NodeList'}, Object.getOwnPropertyDescriptors(x))",
    ],
)
@pytest.mark.requires_dynamic_linking
@run_in_pyodide
def test_array_sequence_methods(selenium, sequence_converter):
    from pytest import raises

    from js import ArrayBuffer
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    x = to_js([77, 65, 23])
    l = run_js(sequence_converter)(x)
    from ctypes import c_bool, c_ssize_t, py_object, pythonapi

    pythonapi.PySequence_Check.argtypes = [py_object]
    pythonapi.PySequence_Check.restype = c_bool
    pythonapi.PySequence_Length.argtypes = [py_object]
    pythonapi.PySequence_GetItem.argtypes = [py_object, c_ssize_t]
    pythonapi.PySequence_GetItem.restype = py_object
    pythonapi.PySequence_SetItem.argtypes = [py_object, c_ssize_t, py_object]
    pythonapi.PySequence_DelItem.argtypes = [py_object, c_ssize_t]

    assert pythonapi.PySequence_Check(l)
    assert pythonapi.PySequence_Length(l) == 3
    assert pythonapi.PySequence_GetItem(l, 0) == 77

    node_list = "NodeList" in str(l)
    typed_array = ArrayBuffer.isView(l)
    is_mutable = not node_list
    supports_del = not (node_list or typed_array)

    if typed_array:
        with raises(TypeError, match=r"unsupported operand type\(s\) for \+"):
            l + [4, 5, 6]
    else:
        assert (l + [4, 5, 6]).to_py() == [77, 65, 23, 4, 5, 6]

    if is_mutable:
        pythonapi.PySequence_SetItem(l, 1, 29)
        assert l[1] == 29
        l[1] = 65
    else:
        with raises(TypeError, match="does ?n[o']t support item assignment"):
            pythonapi.PySequence_SetItem(l, 1, 29)
        assert l[1] == 65

    if supports_del:
        pythonapi.PySequence_DelItem(l, 1)
        assert l.to_py() == [77, 23]
    else:
        with raises(TypeError, match="does ?n[o']t support item deletion"):
            pythonapi.PySequence_DelItem(l, 1)
        assert list(l) == [77, 65, 23]


@run_in_pyodide
def test_array_sequence_repeat(selenium):
    from pyodide.ffi import JsArray, to_js

    a = [77, 65, 23]
    l: JsArray[int] = to_js(a)

    assert (l * 0).to_py() == a * 0
    assert (l * 1).to_py() == a * 1
    assert (l * 2).to_py() == a * 2

    l *= 0
    assert list(l) == a * 0
    l = to_js(a)
    l *= 1
    assert list(l) == a * 1
    l = to_js(a)
    l *= 2
    assert list(l) == a * 2


@run_in_pyodide
def test_jsproxy_match(selenium):
    from pyodide.code import run_js

    x: int
    y: int
    l: list[int]

    a = run_js("[1, 2, 3]")
    match a:
        case [x, y, 3]:
            pass
    assert x == 1
    assert y == 2

    b = run_js("new Uint8Array([7, 3, 9, 10])")
    match b:
        case [x, y, *l]:
            pass
    assert x == 7
    assert y == 3
    assert l == [9, 10]

    c = run_js("new Map([[1,2], [3,4]])")
    match c:
        case {1: x, 3: y}:
            pass
    assert x == 2
    assert y == 4

    c = run_js("({a: 2, b: 5})").as_object_map()
    match c:
        case {"a": x, "b": y}:
            pass
    assert x == 2
    assert y == 5
    default = False
    match c:
        case {"a": x, "b": y, "d": _}:
            pass
        case _:
            default = True
    assert default


@run_in_pyodide
def test_jsarray_index(selenium):
    import pytest

    from pyodide.code import run_js

    a = run_js("[5, 7, 9, -1, 3, 5]")
    assert a.index(5) == 0
    assert a.index(5, 1) == 5
    with pytest.raises(ValueError, match="5 is not in list"):
        assert a.index(5, 1, -1) == 5

    a.append([1, 2, 3])
    assert a.index([1, 2, 3]) == 6
    run_js("(a) => a.pop().destroy()")(a)


@run_in_pyodide
def test_jsarray_count(selenium):
    from pyodide.code import run_js

    l = [5, 7, 9, -1, 3, 5]
    a = run_js(repr(l))
    assert a.count(1) == 0
    assert a.count(-1) == 1
    assert a.count(5) == 2

    b = run_js(f"new Int8Array({repr(l)})")
    assert b.count(1) == 0
    assert b.count(-1) == 1
    assert b.count(5) == 2

    a.append([])
    a.append([1])
    a.append([])
    assert a.count([]) == 2
    assert a.count([1]) == 1
    assert a.count([2]) == 0
    run_js(
        """(a) => {
            a.pop().destroy();
            a.pop().destroy();
            a.pop().destroy();
        }
        """
    )(a)


@run_in_pyodide
def test_jsarray_remove(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import create_proxy

    l = [5, 7, 9, -1, 3, 5]
    a = run_js(repr(l))
    l.remove(5)
    a.remove(5)
    with pytest.raises(ValueError, match="is not in list"):
        a.remove(78)
    assert a.to_py() == l
    l.append([])  # type:ignore[arg-type]
    p = create_proxy([], roundtrip=False)  # type:ignore[var-annotated]
    a.append(p)
    assert a.to_py() == l
    l.remove([])  # type:ignore[arg-type]
    a.remove([])
    p.destroy()
    assert a.to_py() == l
    a.push([])
    with pytest.raises(ValueError, match="is not in list"):
        a.remove([])


@run_in_pyodide
def test_jsarray_insert(selenium):
    from pyodide.code import run_js

    l = [5, 7, 9, -1, 3, 5]
    a = run_js(repr(l))
    l.insert(3, 66)
    a.insert(3, 66)
    assert a.to_py() == l
    l.insert(-1, 97)
    a.insert(-1, 97)
    assert a.to_py() == l


@run_in_pyodide
def test_jsproxy_descr_get(selenium):
    from pyodide.code import run_js

    class T:
        a: int
        b: int
        f = run_js("function f(x) {return this[x]; }; f")

    t = T()
    t.a = 7
    t.b = 66
    assert t.f("a") == 7
    assert t.f("b") == 66
    assert t.f("c") is None


@run_in_pyodide
def test_mappings(selenium):
    import pytest

    from pyodide.code import run_js

    m = run_js("new Map([[1,2], [3,4]])")
    # Iterate using keys() function
    assert set(m) == {1, 3}
    assert 1 in m.keys()
    assert m.keys() | {2} == {1, 2, 3}
    assert 2 in m.values()
    assert set(m.values()) == {2, 4}
    assert (1, 2) in m.items()
    assert set(m.items()) == {(1, 2), (3, 4)}

    assert m.get(1, 7) == 2
    assert m.get(2, 7) == 7

    assert m.pop(1) == 2
    assert m.pop(1, 7) == 7
    m[1] = 2
    assert m.pop(1, 7) == 2
    assert m.pop(1, 7) == 7
    assert 1 not in m
    with pytest.raises(KeyError):
        m.pop(1)

    assert m.setdefault(1, 8) == 8
    assert m.setdefault(3, 8) == 4
    assert m.setdefault(3) == 4
    assert m.setdefault(4) is None
    assert 1 in m
    assert m[1] == 8

    m.update({6: 7, 8: 9})
    assert dict(m) == {1: 8, 3: 4, 4: None, 6: 7, 8: 9}

    assert m.popitem() in set({1: 8, 3: 4, 4: None, 6: 7, 8: 9}.items())
    assert len(m) == 4
    m.clear()
    assert dict(m) == {}


@run_in_pyodide
def test_jsproxy_as_object_map(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsMutableMap

    o1 = run_js("({a : 2, b: 3, c: 77, 1 : 9})")
    with pytest.raises(TypeError, match="object is not subscriptable"):
        o1["a"]
    o = o1.as_object_map()
    assert not isinstance(o1, JsMutableMap)
    assert isinstance(o, JsMutableMap)
    del o1
    assert len(o) == 4
    assert set(o) == {"a", "b", "c", "1"}
    assert "a" in o
    assert "b" in o
    assert "1" in o
    assert 1 not in o
    assert o["a"] == 2
    assert o["1"] == 9
    del o["a"]
    assert "a" not in o
    assert not hasattr(o, "a")
    assert hasattr(o, "b")
    assert len(o) == 3
    assert set(o) == {"b", "c", "1"}
    o["d"] = 36
    assert len(o) == 4
    with pytest.raises(
        TypeError, match="Can only assign keys of type string to JavaScript object map"
    ):
        o[1] = 2
    assert len(o) == 4
    assert set(o) == {"b", "c", "d", "1"}
    assert o["d"] == 36
    assert "constructor" not in o
    assert o.to_py() == {"b": 3, "c": 77, "d": 36, "1": 9}

    with pytest.raises(KeyError):
        del o[1]


@run_in_pyodide
def test_object_map_mapping_methods(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsMap, JsMutableMap

    m = run_js("({1:2, 3:4})").as_object_map()
    assert isinstance(m, JsMap)
    assert isinstance(m, JsMutableMap)
    # Iterate using keys() function
    assert set(m) == {"1", "3"}
    assert "1" in m.keys()
    assert 1 not in m.keys()
    assert m.keys() | {"2"} == {"1", "2", "3"}
    assert 2 in m.values()
    assert set(m.values()) == {2, 4}
    assert ("1", 2) in m.items()
    assert set(m.items()) == {("1", 2), ("3", 4)}

    assert m.get("1", 7) == 2
    assert m.get("2", 7) == 7

    assert m.pop("1") == 2
    assert m.pop("1", 7) == 7
    m["1"] = 2
    assert m.pop("1", 7) == 2
    assert m.pop("1", 7) == 7
    assert "1" not in m
    with pytest.raises(KeyError):
        m.pop("1")

    assert m.setdefault("1", 8) == 8
    assert m.setdefault("3", 8) == 4
    assert m.setdefault("3") == 4
    assert m.setdefault("4") is None
    assert "1" in m
    assert m["1"] == 8

    m.update({"6": 7, "8": 9})
    assert dict(m) == {"1": 8, "3": 4, "4": None, "6": 7, "8": 9}

    assert m.popitem() in set({"1": 8, "3": 4, "4": None, "6": 7, "8": 9}.items())
    assert len(m) == 4
    m.clear()
    assert dict(m) == {}


@run_in_pyodide
def test_as_object_map_heritable(selenium):
    import pytest
    from _pyodide_core import js_flags

    from pyodide.code import run_js
    from pyodide.ffi import JsMutableMap

    flag = js_flags["IS_OBJECT_MAP"]

    o = run_js("({1:{2: 9, 3: 77}, 3:{6: 5, 12: 3, 2: 9}})")
    mh = o.as_object_map(hereditary=True)
    mn = o.as_object_map(hereditary=False)

    assert mh._js_type_flags & flag != 0
    assert mn._js_type_flags & flag != 0
    assert isinstance(mh, JsMutableMap)
    assert isinstance(mn, JsMutableMap)

    assert mh["1"]._js_type_flags & flag != 0
    assert mn["1"]._js_type_flags & flag == 0
    assert isinstance(mh["1"], JsMutableMap)
    assert not isinstance(mn["1"], JsMutableMap)

    assert mh["1"]["3"] == 77

    with pytest.raises(TypeError):
        mn["1"]["3"]

    for x in mh.values():
        assert x["2"] == 9

    for x in mn.values():
        with pytest.raises(TypeError):
            x["2"]

    n = mh.pop("1")
    assert n["3"] == 77

    o = run_js(
        """({0:[], 1:new Uint8Array(), 2:new Error(), 3:new ArrayBuffer()})"""
    ).as_object_map(hereditary=True)
    assert o["0"]._js_type_flags & flag == 0
    assert o["1"]._js_type_flags & flag == 0
    assert o["2"]._js_type_flags & flag == 0
    assert o["3"]._js_type_flags & flag == 0

    o = run_js("""({1:{get(){}, 2: 1}, 2:new Map([["a", 1]])})""").as_object_map(
        hereditary=True
    )
    assert o["1"]._js_type_flags & flag != 0
    assert o["2"]._js_type_flags & flag != 0
    assert "2" in o["1"]
    assert "a" not in o["2"]


@run_in_pyodide
def test_as_object_map_presence(selenium):
    from pyodide.code import run_js

    for meth in ["[Symbol.iterator]", "get", "set"]:
        o = run_js(
            "({ %s(){} })" % meth,
        )
        assert hasattr(o, "as_object_map")
        assert hasattr(o, "as_py_json")

    o = run_js("[]")
    assert not hasattr(o, "as_object_map")
    assert hasattr(o, "as_py_json")

    for s in [
        "({ next(){} })",
        "new Uint8Array()",
        "new ArrayBuffer()",
        "new Error()",
        "() => {}",
    ]:
        o = run_js(s)
        assert not hasattr(o, "as_object_map")
        assert not hasattr(o, "as_py_json")


@run_in_pyodide
def test_as_py_json(selenium):
    from _pyodide_core import js_flags

    from js import JSON
    from pyodide.code import run_js
    from pyodide.ffi import JsArray, JsMap, JsProxy

    dict_flag = js_flags["IS_PY_JSON_DICT"]
    seq_flag = js_flags["IS_PY_JSON_SEQUENCE"]
    either_flag = dict_flag | seq_flag

    o = run_js("({a: [1,2, {b: 7}]})").as_py_json()
    assert o._js_type_flags & dict_flag
    assert isinstance(o, JsMap)
    assert "a" in o
    assert len(o) == 1
    assert o["a"]._js_type_flags & seq_flag != 0
    assert len(o["a"]) == 3
    assert o["a"][0] == 1
    assert o["a"][-1]._js_type_flags & dict_flag != 0
    assert len(o["a"][-1]) == 1
    assert o["a"][-1]["b"] == 7

    assert list(o.keys()) == ["a"]
    assert [(k, v.to_py()) for (k, v) in o.items()] == [("a", [1, 2, {"b": 7}])]

    o2 = run_js("([[1, 2], ()=>{}])").as_py_json()
    assert o2._js_type_flags & seq_flag != 0
    assert o2[0]._js_type_flags & seq_flag != 0
    assert o2[1]._js_type_flags & either_flag == 0

    a = run_js("([{b: 1}, {b: 3}, {b: 7}])").as_py_json()
    l = [e["b"] for e in a]
    assert l == [1, 3, 7]
    import json

    def default(obj):
        if isinstance(obj, JsProxy):
            if isinstance(obj, JsArray):
                return list(obj)
            if isinstance(obj, JsMap):
                return dict(obj)
        raise NotImplementedError

    for x in [o, a]:
        assert json.dumps(x, default=default).replace(" ", "") == JSON.stringify(x)
        assert json.loads(json.dumps(x, default=default)) == x.to_py()


@run_in_pyodide
def test_jsproxy_subtypes(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsArray, JsBuffer, JsPromise, JsProxy

    with pytest.raises(TypeError, match="JsProxy"):
        JsProxy()

    with pytest.raises(TypeError, match="JsArray"):
        JsArray()

    nullobj = run_js("Object.create(null)")
    a = run_js("[Promise.resolve()]")
    assert isinstance(a, JsProxy)
    assert isinstance(a, JsArray)
    assert not isinstance(a, JsPromise)
    assert not isinstance(a, JsBuffer)
    assert issubclass(type(a), JsProxy)
    assert issubclass(type(a), JsArray)
    assert not issubclass(JsArray, type(a))
    assert isinstance(a[0], JsPromise)
    assert issubclass(JsPromise, type(a[0]))
    assert not isinstance(a, JsBuffer)
    assert issubclass(type(a), type(nullobj))
    assert issubclass(type(a[0]), type(nullobj))
    assert issubclass(JsProxy, type(nullobj))
    assert issubclass(type(nullobj), JsProxy)


@run_in_pyodide
def test_gen_send(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator, JsAsyncIterator, JsGenerator, JsIterator

    f = run_js(
        """
        (function*(){
            let n = 0;
            for(let i = 0; i < 3; i++){
                n = yield n + 2;
            }
        });
        """
    )

    it = f()
    assert isinstance(it, JsGenerator)
    assert not isinstance(it, JsAsyncGenerator)
    assert isinstance(it, JsIterator)
    assert not isinstance(it, JsAsyncIterator)

    assert it.send(None) == 2
    assert it.send(2) == 4
    assert it.send(3) == 5
    with pytest.raises(StopIteration):
        it.send(4)


@run_in_pyodide
def test_gen_send_type_errors(selenium):
    from re import escape

    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncIterator, JsGenerator, JsIterator

    g = run_js(
        """
        ({next(){ return 2; }});
        """
    )
    assert isinstance(g, JsIterator)
    assert isinstance(g, JsAsyncIterator)
    assert not isinstance(g, JsGenerator)
    with pytest.raises(
        TypeError, match='Result should have type "object" not "number"'
    ):
        g.send(None)  # type:ignore[attr-defined]

    g = run_js(
        """
        ({next(){ return Promise.resolve(2); }});
        """
    )
    with pytest.raises(
        TypeError,
        match=escape("Result was a promise, use anext() / asend() / athrow() instead."),
    ):
        g.send(None)

    g = run_js(
        """
        ({next(){ return {}; }});
        """
    )
    with pytest.raises(TypeError, match='Result has no "done" field.'):
        g.send(None)


@run_in_pyodide
def test_gen_throw(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsGenerator

    f = run_js(
        """
        (function *() {
            try {
                yield 1;
            } finally {
                yield 2;
                console.log("finally");
            }
        })
        """
    )

    g = f()
    assert isinstance(g, JsGenerator)
    assert next(g) == 1
    assert g.throw(TypeError("hi")) == 2
    with pytest.raises(TypeError, match="hi"):
        next(g)

    g = f()
    assert next(g) == 1
    assert g.throw(TypeError, "hi") == 2
    with pytest.raises(TypeError, match="hi"):
        next(g)

    f = run_js(
        """
        (function *() {
            yield 1;
            yield 2;
            yield 3;
        })
        """
    )
    g = f()
    assert next(g) == 1
    g.close()


@run_in_pyodide
def test_gen_close(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsGenerator

    f = run_js(
        """
        (function *(x) {
            try {
                yield 1;
                yield 2;
                x.push("this never happens");
                yield 3;
            } finally {
                x.append("finally");
            }
        })
        """
    )

    from pyodide.ffi import create_proxy

    l: list[str] = []
    p = create_proxy(l)
    g = f(p)
    assert isinstance(g, JsGenerator)
    assert next(g) == 1
    assert next(g) == 2
    assert g.close() is None  # type:ignore[func-returns-value]
    p.destroy()
    assert l == ["finally"]

    f = run_js(
        """
        (function *(x) {
            try {
                yield 1;
            } finally {
                yield 2;
            }
        })
        """
    )

    g = f()
    next(g)
    with pytest.raises(RuntimeError, match="JavaScript generator ignored return"):
        g.close()


@run_in_pyodide
async def test_agen_aiter(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator, JsAsyncIterator, JsGenerator, JsIterator

    f = run_js(
        """
        (async function *(){
            yield 2;
            yield 3;
            return 7;
        })
        """
    )
    b = f()
    assert isinstance(b, JsAsyncIterator)
    assert not isinstance(b, JsIterator)
    assert isinstance(b, JsAsyncGenerator)
    assert not isinstance(b, JsGenerator)
    assert await anext(b) == 2
    assert await anext(b) == 3
    with pytest.raises(StopAsyncIteration):
        await anext(b)

    g = run_js(
        """
        (function *(){
            yield 2;
            yield 3;
            return 7;
        })()
        """
    )

    assert not isinstance(g, JsAsyncIterator)
    assert isinstance(g, JsIterator)
    assert not isinstance(g, JsAsyncGenerator)
    assert isinstance(g, JsGenerator)


@run_in_pyodide
async def test_agen_aiter2(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncIterable, JsAsyncIterator, JsIterable, JsIterator

    iterable = run_js(
        """
        ({
        [Symbol.asyncIterator]() {
            return (async function *f(){yield 1; yield 2; yield 3;})();
        }
        })
        """
    )
    assert not isinstance(iterable, JsIterable)
    assert isinstance(iterable, JsAsyncIterable)

    with pytest.raises(TypeError, match="object is not iterable"):
        iter(iterable)  # type:ignore[call-overload]

    it = aiter(iterable)
    assert isinstance(it, JsAsyncIterator)
    assert not isinstance(it, JsIterator)

    assert await anext(it) == 1
    assert await anext(it) == 2
    assert await anext(it) == 3
    with pytest.raises(StopAsyncIteration):
        await anext(it)


@run_in_pyodide
async def test_agen_asend(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator, JsIterator

    it = run_js(
        """
        (async function*(){
            let n = 0;
            for(let i = 0; i < 3; i++){
                n = yield n + 2;
            }
        })();
        """
    )

    assert isinstance(it, JsAsyncGenerator)
    assert not isinstance(it, JsIterator)

    assert await it.asend(None) == 2
    assert await it.asend(2) == 4
    assert await it.asend(3) == 5
    with pytest.raises(StopAsyncIteration):
        await it.asend(4)


# pytest.mark.xfail("async error gets converted into double wrapped error")
@run_in_pyodide
async def test_agen_athrow(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator, JsException

    f = run_js(
        """
        (async function *() {
            try {
                yield 1;
            } finally {
                yield 2;
                console.log("finally");
            }
        })
        """
    )

    g = f()
    assert isinstance(g, JsAsyncGenerator)
    assert await anext(g) == 1
    assert await g.athrow(TypeError("hi")) == 2
    # TODO: figure out how to make this raise a TypeError!
    with pytest.raises(JsException, match="hi"):
        await anext(g)

    g = f()
    assert isinstance(g, JsAsyncGenerator)
    assert await anext(g) == 1
    assert await g.athrow(TypeError, "hi") == 2
    with pytest.raises(JsException, match="hi"):
        await anext(g)

    f = run_js(
        """
        (async function *() {
            yield 1;
            yield 2;
            yield 3;
        })
        """
    )
    g = f()
    assert isinstance(g, JsAsyncGenerator)
    assert await anext(g) == 1
    await g.aclose()


@run_in_pyodide
async def test_agen_aclose(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator

    f = run_js(
        """
        (async function *(x) {
            try {
                yield 1;
                yield 2;
                x.push("this never happens");
                yield 3;
            } finally {
                x.append("finally");
            }
        })
        """
    )

    from pyodide.ffi import create_proxy

    l: list[str] = []
    p = create_proxy(l)
    g = f(p)
    assert isinstance(g, JsAsyncGenerator)
    assert await anext(g) == 1
    assert await anext(g) == 2
    assert await g.aclose() is None  # type:ignore[func-returns-value]
    assert await g.aclose() is None  # type:ignore[func-returns-value]
    p.destroy()
    assert l == ["finally"]


@run_in_pyodide
def test_gen_lifetimes(selenium):
    import sys

    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsGenerator

    # Check that:
    # 1. The lifetime of the generator argument is extended
    # 2. The lifetime of the objects we `send` to the generator are extended
    # 3. The returned pyproxy is successfully received in JavaScript
    # 4. The returned pyproxy is destroyed
    f = run_js(
        """
        (function *(x) {
            let l = [x];
            l.push(yield);
            l.push(yield);
            l.push(yield);
            return pyodide.toPy(l.map((x) => x.toString()));
        })
        """
    )
    g = f({1})
    assert isinstance(g, JsGenerator)
    g.send(None)
    g.send({2})
    g.send({3})
    with pytest.raises(StopIteration) as exc_info:
        g.send({4})

    v = exc_info.value.value
    del exc_info
    assert v == ["{1}", "{2}", "{3}", "{4}"]
    assert sys.getrefcount(v) == 2


@run_in_pyodide
async def test_agen_lifetimes(selenium):
    import sys
    from asyncio import sleep

    from pyodide.code import run_js
    from pyodide.ffi import JsAsyncGenerator

    # Check that:
    # 1. The lifetime of the generator argument is extended
    # 2. The lifetime of the objects we `asend` to the generator are extended
    # 3. The returned pyproxy is successfully received in JavaScript
    # 4. The returned pyproxy is destroyed
    f = run_js(
        """
        (async function *(x) {
            let l = [x];
            l.push(yield);
            l.push(yield);
            l.push(yield);
            return pyodide.toPy(l.map((x) => x.toString()));
        })
        """
    )
    g = f({1})
    assert isinstance(g, JsAsyncGenerator)
    await g.asend(None)
    await g.asend({2})
    await g.asend({3})
    # This approach is a bit odd but it gets the refcount right. In various
    # other ways, someone else holds on to a reference to the exception.
    res = g.asend({4})
    await sleep(0.01)
    v = res.exception().args[0]  # type:ignore[attr-defined]
    del res
    assert v == ["{1}", "{2}", "{3}", "{4}"]
    assert sys.getrefcount(v) == 2


@run_in_pyodide
def test_python_reserved_keywords(selenium):
    import pytest

    from pyodide.code import run_js

    o = run_js(
        """({
            async: 1,
            await: 2,
            False: 3,
            nonlocal: 4,
            yield: 5,
            try: 6,
            assert: 7,
            match: 222,
        })
        """
    )
    assert o.match == 222
    with pytest.raises(AttributeError):
        o.match_  # noqa: B018
    assert eval("o.match") == 222
    keys = ["async", "await", "False", "nonlocal", "yield", "try", "assert"]
    for k in keys:
        with pytest.raises(SyntaxError):
            eval(f"o.{k}")

    assert o.async_ == 1
    assert o.await_ == 2
    assert o.False_ == 3
    assert o.nonlocal_ == 4
    assert o.yield_ == 5
    assert o.try_ == 6
    assert o.assert_ == 7
    expected_set = {k + "_" for k in keys} | {"match"}
    actual_set = set(dir(o)) & expected_set
    assert actual_set == expected_set
    assert set(dir(o)) & set(keys) == set()
    o.async_ = 2
    assert run_js("(o) => o.async")(o) == 2
    del o.async_
    assert run_js("(o) => o.async")(o) is None

    o = run_js("({async: 1, async_: 2, async__: 3})")
    expected_set = {"async_", "async__", "async___"}
    actual_set = set(dir(o)) & expected_set
    assert actual_set == expected_set
    assert o.async_ == 1
    assert o.async__ == 2
    assert o.async___ == 3
    assert getattr(o, "async_") == 1  # noqa: B009
    assert getattr(o, "async__") == 2  # noqa: B009
    assert getattr(o, "async") == 1

    assert hasattr(o, "async_")
    assert hasattr(o, "async")
    setattr(o, "async", 2)
    assert o.async_ == 2
    delattr(o, "async")
    assert not hasattr(o, "async_")
    assert not hasattr(o, "async")


@run_in_pyodide
def test_revoked_proxy(selenium):
    """I think this is just about the worst thing that it is possible to
    make.

    A good stress test for our systems...
    """
    from pyodide.code import run_js

    x = run_js("(p = Proxy.revocable({}, {})); p.revoke(); p.proxy")
    run_js("((x) => x)")(x)


@run_in_pyodide
def test_js_proxy_attribute(selenium):
    # Check that `in` is only consulted as a fallback if indexing returns None
    import pytest

    from pyodide.code import run_js

    x = run_js(
        """
        new Proxy(
            {},
            {
                get(target, val) {
                    return { a: 3, b: 7, c: undefined, d: undefined }[val];
                },
                has(target, val) {
                    return { a: true, b: false, c: true, d: false }[val];
                },
            }
        );
        """
    )
    assert x.a == 3
    assert x.b == 7  # Previously this raised AttributeError
    assert x.c is None
    with pytest.raises(AttributeError):
        x.d  # noqa: B018


@run_in_pyodide
async def test_js_proxy_str(selenium):
    import re

    import pytest

    from js import Array
    from pyodide.code import run_js
    from pyodide.ffi import JsException

    assert (
        re.sub(r"\s+", " ", str(Array).replace("\n", " "))
        == "function Array() { [native code] }"
    )
    assert str(run_js("[1,2,3]")) == "1,2,3"
    assert str(run_js("Object.create(null)")) == "[object Object]"
    mod = await run_js("import('data:text/javascript,')")
    assert str(mod) == "[object Module]"
    # accessing toString fails, should fall back to Object.prototype.toString.call
    x = run_js(
        """
        ({
          get toString() {
            throw new Error();
          },
          [Symbol.toStringTag] : "SomeTag"
        })
        """
    )
    assert str(x) == "[object SomeTag]"
    # accessing toString succeeds but toString call throws, let exception propagate
    x = run_js(
        """
        ({
          toString() {
            throw new Error("hi!");
          },
        })
        """
    )
    with pytest.raises(JsException, match="hi!"):
        str(x)

    # No toString method, so we fall back to Object.prototype.toString.call
    # which throws, let error propagate
    x = run_js(
        """
        ({
          get [Symbol.toStringTag]() {
            throw new Error("hi!");
          },
        });
        """
    )
    with pytest.raises(JsException, match="hi!"):
        str(x)

    # accessing toString fails, so fall back to Object.prototype.toString.call
    # which also throws, let error propagate
    px = run_js("(p = Proxy.revocable({}, {})); p.revoke(); p.proxy")
    with pytest.raises(
        JsException,
        match="revoked",
    ):
        str(px)


@run_in_pyodide
def test_bind_jsfunc_sig(selenium):
    from _pyodide.jsbind import func_to_sig_inner

    def f(
        a: dict[str, int],
        /,
    ) -> list[int]:
        raise NotImplementedError

    assert (
        repr(func_to_sig_inner(f, None))
        == "<JsSignature (a: dict[str, int], /) -> list[int]>"
    )


@run_in_pyodide
def test_bind_func_illegal_sigs(selenium):
    from typing import no_type_check

    import pytest

    from pyodide.code import run_js

    jsfunc = run_js("(...args) => pyodide.toPy(args)")

    def func(a):
        pass

    with pytest.raises(RuntimeError, match="Don't currently handle POS_OR_KWD args"):
        jsfunc.bind_sig(func)(1)

    @no_type_check
    def get_bound(sig):
        d = {}
        exec(f"def func({sig}): ...", d)
        func = d.pop("func")
        return jsfunc.bind_sig(func)

    func = get_bound("*," + ", ".join([f"a{n}" for n in range(65)]))
    with pytest.raises(
        RuntimeError, match="Cannot handle function with more than 64 kwonly args"
    ):
        func()  # type:ignore[call-arg]

    kwargs = {f"a{n}": 0 for n in range(64)}
    func = get_bound("*," + ", ".join([f"a{n}" for n in range(64)]))
    assert func(**kwargs) == [kwargs]
    del kwargs["a63"]
    with pytest.raises(
        TypeError, match="func.. missing 1 required keyword-only argument: 'a63'"
    ):
        func(**kwargs)


@no_type_check
@pytest.mark.parametrize(
    "sig",
    [
        "",
        "a, /",
        "a, b, /",
        "a=7, /",
        "a, b=7, /",
        "a, b=7, /, *, c",
        "a, b=7, /, *, c=None",
        "a, b=7, /, *, c=2",
        "a, b=7, /, **kwargs",
        "a, b=7, /, **kwargs",
        "a, b=7, /, *, c=None, **kwargs",
        "a, b=7, /, *, c, **kwargs",
    ],
)
@run_in_pyodide
def test_bind_arg_checking(selenium, sig):
    from inspect import Parameter, signature

    import pytest

    from pyodide.code import run_js

    d = {}
    exec(f"def func({sig}): ...", d)
    func = d.pop("func")

    f = run_js("(...args) => pyodide.toPy(args)").bind_sig(func)

    def check(*args, **kwargs):
        err = None
        try:
            try:
                func(*args, **kwargs)
            except TypeError as e:
                err = e

            if err:
                with pytest.raises(TypeError) as e:
                    f(*args, **kwargs)
                assert e.value.args[0] == err.args[0]
                return

            sig = signature(func)
            # rename positional parameters to work around bug in bind
            # https://github.com/python/cpython/issues/87106
            new_params = []
            for p in sig.parameters.values():
                if p.kind == Parameter.POSITIONAL_ONLY:
                    p = p.replace(name=f"__{p.name}")
                new_params.append(p)
            sig = sig.replace(parameters=new_params)
            res = sig.bind(*args, **kwargs)
            res.apply_defaults()
            expected = [*res.args]
            reskwargs = dict(res.kwargs)
            if reskwargs:
                expected.append(reskwargs)
            for k, v in list(reskwargs.items()):
                if v is None:
                    del reskwargs[k]
            assert f(*args, **kwargs) == expected
        finally:
            err = None

    check()
    check(1)
    check(1, 2)
    check(1, 2, 3)

    check(x=1)
    check(1, x=1)
    check(1, 2, 3, x=1)

    check(x=1, y=1)
    check(1, x=1, y=1)
    check(1, 2, x=1, y=1)

    check(a=1)
    check(1, b=1)
    check(1, a=1)

    check(c=2)
    check(1, c=2)
    check(1, 2, c=2)
    check(1, 2, 3, c=2)

    check(1, 2, b=2)
    check(1, b=2, c=2)


@run_in_pyodide
def test_bind_self_reference(selenium):
    from _pyodide.jsbind import BindClass
    from pyodide.code import run_js

    a = run_js("({f() { return this; }})")
    a.a = a

    global A  # noqa: PLW0603

    class A(BindClass):
        a: "A"

        @staticmethod
        def f() -> "A":
            return A()

    # Hack to fix type name resolution. Once we merge
    # https://github.com/pyodide/pytest-pyodide/pull/133
    # it won't be needed anymore.
    A.A = A  # type:ignore[attr-defined]

    a = a.bind_sig(A)

    assert a._sig == A
    assert a.a._sig == A
    assert a.a.a._sig == A
    assert a.f()._sig == A


@run_in_pyodide
def test_jsproxy_no_error_this(selenium):
    from pyodide.code import run_js

    # thisArg should be null and not JS_ERROR
    test = run_js(
        """
        () => new Proxy(() => 1, {
            apply(target, thisArg, argumentsList) {
                return thisArg === null;
            }
        })
        """
    )
    assert test()()
