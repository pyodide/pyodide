# See also test_typeconversions, and test_python.
import pytest
from pyodide_build.testing import run_in_pyodide


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
    jsproxy_items = set(
        [
            "__bool__",
            "__class__",
            "__defineGetter__",
            "__defineSetter__",
            "__delattr__",
            "constructor",
            "toString",
            "typeof",
            "valueOf",
        ]
    )
    a_items = set(["x", "y"])
    callable_items = set(["__call__", "new"])
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
    assert (
        selenium.run_js(
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
        )
        == [2, "9", "object"]
    )


def test_jsproxy_document(selenium):
    if selenium.browser == "node":
        pytest.xfail("No document in node")
    selenium.run("from js import document")
    assert (
        selenium.run(
            """
            el = document.createElement('div')
            document.body.appendChild(el)
            document.body.children.length
            """
        )
        == 1
    )
    assert selenium.run("document.body.children[0].tagName") == "DIV"
    assert selenium.run("repr(document)") == "[object HTMLDocument]"
    assert (
        selenium.run(
            """
            from js import document
            el = document.createElement('div')
            len(dir(el)) >= 200 and 'appendChild' in dir(el)
            """
        )
        is True
    )
    assert (
        selenium.run(
            """
            from js import ImageData
            ImageData.new(64, 64).width
            """
        )
        == 64
    )
    assert (
        selenium.run(
            """
            from js import ImageData
            ImageData.typeof
            """
        )
        == "function"
    )


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


def test_jsproxy_map(selenium):
    selenium.run_js(
        """
        self.TEST = new Map([["x", 42], ["y", 43]]);
        """
    )
    assert (
        selenium.run(
            """
            from js import TEST
            del TEST['y']
            'y' in TEST
            """
        )
        is False
    )
    assert selenium.run(
        """
        from js import TEST
        TEST == TEST
        """
    )
    assert selenium.run(
        """
        from js import TEST
        TEST != 'foo'
        """
    )
    selenium.run_js(
        """
        self.TEST = {foo: 'bar', baz: 'bap'}
        """
    )
    assert (
        selenium.run(
            """
            from js import TEST
            dict(TEST.object_entries()) == {'foo': 'bar', 'baz': 'bap'}
            """
        )
        is True
    )


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
    assert selenium.run("from js import ITER\n" "list(ITER)") == [1, 2, 3]


def test_jsproxy_implicit_iter(selenium):
    selenium.run_js(
        """
        self.ITER = [1, 2, 3];
        """
    )
    assert selenium.run("from js import ITER, Object\n" "list(ITER)") == [1, 2, 3]
    assert selenium.run("from js import ITER, Object\n" "list(ITER.values())") == [
        1,
        2,
        3,
    ]
    assert selenium.run(
        "from js import ITER, Object\n" "list(Object.values(ITER))"
    ) == [1, 2, 3]


def test_jsproxy_call(selenium):
    assert (
        selenium.run_js(
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
        )
        == list(range(10))
    )


def test_jsproxy_call_kwargs(selenium):
    assert (
        selenium.run_js(
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
        )
        == [10, 2]
    )


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
        """
        let y;
        self.f = function(x){ y = x; }
        pyodide.runPython(`
            from js import f
            f({})
            f([])
        `);
        assertThrows(() => y.length, "Error", "This borrowed proxy was automatically destroyed");
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
            if(pyodide.isPyProxy(self.myGlobal)){
                self.myGlobal.destroy();
            }
            if(pyodide.isPyProxy(x)){
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
            if(pyodide.isPyProxy(self.myGlobal)){
                self.myGlobal.destroy();
            }
            if(pyodide.isPyProxy(x)){
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
def test_import_invocation():
    import js

    def temp():
        print("okay?")

    from pyodide import create_once_callable

    js.setTimeout(create_once_callable(temp), 100)
    js.fetch("packages.json")


@run_in_pyodide
def test_import_bind():
    from js import fetch

    fetch("packages.json")


@run_in_pyodide
def test_nested_attribute_access():
    import js
    from js import self

    assert js.Float64Array.BYTES_PER_ELEMENT == 8
    assert self.Float64Array.BYTES_PER_ELEMENT == 8


@run_in_pyodide
def test_window_isnt_super_weird_anymore():
    import js
    from js import self, Array

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
    assert set([x for x in result[3] if len(x) == 1]) == set(["x", "y", "s", "t"])
    assert set([x for x in result[4] if len(x) == 1]) == set(["x", "y", "u", "t"])
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


def test_object_entries_keys_values(selenium):
    selenium.run_js(
        """
        self.x = { a : 2, b : 3, c : 4 };
        pyodide.runPython(`
            from js import x
            assert x.object_entries().to_py() == [["a", 2], ["b", 3], ["c", 4]]
            assert x.object_keys().to_py() == ["a", "b", "c"]
            assert x.object_values().to_py() == [2, 3, 4]
        `);
        """
    )


def test_mixins_feature_presence(selenium):
    result = selenium.run_js(
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
        await pyodide.runPythonAsync(`
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

            from pyodide import JsException
            msg = "^TypeError:.* is not a function$"
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


def test_mixins_errors_3(selenium):
    selenium.run_js(
        """
        self.l = [0, false, NaN, undefined, null];
        self.l[6] = 7;
        await pyodide.runPythonAsync(`
            from unittest import TestCase
            raises = TestCase().assertRaises
            from js import l
            with raises(IndexError):
                l[10]
            with raises(IndexError):
                l[5]
            assert len(l) == 7
            l[0]; l[1]; l[2]; l[3]
            l[4]; l[6]
            del l[1]
            with raises(IndexError):
                l[4]
            l[5]
            del l[4]
            l[3]; l[4]
        `);
        """
    )


def test_mixins_errors_4(selenium):
    selenium.run_js(
        """
        self.l = [0, false, NaN, undefined, null];
        self.l[6] = 7;
        let a = Array.from(self.l.entries());
        a.splice(5, 1);
        self.m = new Map(a);
        await pyodide.runPythonAsync(`
            from js import m
            from unittest import TestCase
            raises = TestCase().assertRaises
            with raises(KeyError):
                m[10]
            with raises(KeyError):
                m[5]
            assert len(m) == 6
            m[0]; m[1]; m[2]; m[3]
            m[4]; m[6]
            del m[1]
            with raises(KeyError):
                m[1]
            assert len(m) == 5
        `);
        """
    )


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


def test_buffer_assign_back(selenium):
    result = selenium.run_js(
        """
        self.jsarray = new Uint8Array([1,2,3, 4, 5, 6]);
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
