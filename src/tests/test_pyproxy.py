# See also test_typeconversions, and test_python.
import time

import pytest
from pytest_pyodide.decorator import run_in_pyodide


def test_pyproxy_class(selenium):
    selenium.run_js(
        """
        pyodide.runPython(`
            class Foo:
                bar = 42
                def get_value(self, value):
                    return value * 64
            f = Foo()
        `);
        self.f = pyodide.globals.get('f');
        assert(() => f.type === "Foo");
        let f_get_value = f.get_value
        assert(() => f_get_value(2) === 128);
        f_get_value.destroy();
        assert(() => f.bar === 42);
        assert(() => 'bar' in f);
        f.baz = 32;
        assert(() => f.baz === 32);
        pyodide.runPython(`assert hasattr(f, 'baz')`)
        self.f_props = Object.getOwnPropertyNames(f);
        delete f.baz
        pyodide.runPython(`assert not hasattr(f, 'baz')`)
        assert(() => f.toString().startsWith("<__main__.Foo"));
        f.destroy();
        """
    )
    assert {
        "__class__",
        "__delattr__",
        "__dict__",
        "__dir__",
        "__doc__",
        "__eq__",
        "__format__",
        "__ge__",
        "__getattribute__",
        "__gt__",
        "__hash__",
        "__init__",
        "__init_subclass__",
        "__le__",
        "__lt__",
        "__module__",
        "__ne__",
        "__new__",
        "__reduce__",
        "__reduce_ex__",
        "__repr__",
        "__setattr__",
        "__sizeof__",
        "__str__",
        "__subclasshook__",
        "__weakref__",
        "bar",
        "baz",
        "get_value",
    }.difference(selenium.run_js("return f_props")) == set()


def test_del_builtin(selenium):
    msg = "NameError"
    with pytest.raises(selenium.JavascriptException, match=msg):
        # can't del a builtin
        selenium.run("del open")
    # Can still get it even though we tried to del it.
    assert selenium.run_js(
        """
        let open = pyodide.globals.get("open");
        let result = !!open;
        open.destroy();
        return result;
        """
    )
    assert selenium.run_js("return pyodide.globals.get('__name__');") == "__main__"


def test_in_globals(selenium):
    selenium.run("yyyyy = 7")
    assert (
        selenium.run_js(
            """
            let result = [];
            result.push(pyodide.globals.has("xxxxx"));
            result.push(pyodide.globals.has("yyyyy"));
            result.push(pyodide.globals.has("globals"));
            result.push(pyodide.globals.has("open"));
            return result;
            """
        )
        == [False, True, True, True]
    )


def test_pyproxy_copy(selenium):
    selenium.run_js(
        """
        let d = pyodide.runPython("list(range(10))")
        e = d.copy();
        d.destroy();
        assert(() => e.length === 10);
        e.destroy();
        """
    )


def test_pyproxy_refcount(selenium):
    selenium.run_js(
        """
        function getRefCount(){
            return pyodide.runPython("sys.getrefcount(pyfunc)");
        }
        self.jsfunc = function (f) { f(); };
        pyodide.runPython(`
            import sys
            from js import jsfunc

            def pyfunc(*args, **kwargs):
                print(*args, **kwargs)
        `);

        // the refcount should be 2 because:
        // 1. pyfunc exists
        // 2. pyfunc is referenced from the sys.getrefcount()-test below
        //
        // Each time jsfunc is called a new PyProxy to pyfunc is created. That
        // PyProxy is destroyed when the call finishes, so the calls to
        // jsfunc(pyfunc) do not change the reference count.

        assert(() => getRefCount() === 2);

        pyodide.runPython(`
            jsfunc(pyfunc)
        `);

        assert(() => getRefCount() === 2);

        pyodide.runPython(`
            jsfunc(pyfunc)
            jsfunc(pyfunc)
        `)
        assert(() => getRefCount() === 2);
        pyodide.runPython(`del jsfunc`)
        """
    )


def test_pyproxy_destroy(selenium):
    selenium.run(
        """
        class Foo:
          bar = 42
          def get_value(self, value):
            return value * 64
        f = Foo()
        """
    )

    selenium.run_js(
        """
        let f = pyodide.globals.get('f');
        assert(()=> f.get_value(1) === 64);
        f.destroy();
        assertThrows(() => f.get_value(1), "Error", "already been destroyed");
        """
    )


def test_pyproxy_iter(selenium):
    [ty, l] = selenium.run_js(
        """
        let c = pyodide.runPython(`
            def test():
                for i in range(10):
                    yield i
            test()
        `);
        let result = [c.type, [...c]];
        c.destroy();
        return result;
        """
    )
    assert ty == "generator"
    assert l == list(range(10))

    [ty, l] = selenium.run_js(
        """
        let c = pyodide.runPython(`
            from collections import ChainMap
            ChainMap({"a" : 2, "b" : 3})
        `);
        let result = [c.type, [...c]];
        c.destroy();
        return result;
        """
    )
    assert ty == "ChainMap"
    assert set(l) == {"a", "b"}

    [result, result2] = selenium.run_js(
        """
        let c = pyodide.runPython(`
            def test():
                acc = 0
                for i in range(10):
                    r = yield acc
                    acc += i * r
            test()
        `)
        let {done, value} = c.next();
        let result = [];
        while(!done){
            result.push(value);
            ({done, value} = c.next(value + 1));
        }
        c.destroy();

        function* test(){
            let acc = 0;
            for(let i=0; i < 10; i++){
                let r = yield acc;
                acc += i * r;
            }
        }
        c = test();
        ({done, value} = c.next());
        let result2 = [];
        while(!done){
            result2.push(value);
            ({done, value} = c.next(value + 1));
        }
        return [result, result2];
        """
    )
    assert result == result2


def test_pyproxy_iter_error(selenium):
    selenium.run_js(
        """
        let t = pyodide.runPython(`
            class T:
                def __iter__(self):
                    raise Exception('hi')
            T()
        `);
        assertThrows(() => t[Symbol.iterator](), "PythonError", "hi");
        t.destroy();
        """
    )


def test_pyproxy_iter_error2(selenium):
    selenium.run_js(
        """
        let gen = pyodide.runPython(`
            def g():
                yield 1
                yield 2
                raise Exception('hi')
                yield 3
            g()
        `);
        assert(() => gen.next().value === 1);
        assert(() => gen.next().value === 2);
        assertThrows(() => gen.next(), "PythonError", "hi");
        gen.destroy();
        """
    )


def test_pyproxy_get_buffer(selenium):
    selenium.run_js(
        """
        pyodide.runPython(`
            from sys import getrefcount
            z1 = memoryview(bytes(range(24))).cast("b", [8,3])
            z2 = z1[-1::-1]
        `);
        for(let x of ["z1", "z2"]){
            pyodide.runPython(`assert getrefcount(${x}) == 2`);
            let proxy = pyodide.globals.get(x);
            pyodide.runPython(`assert getrefcount(${x}) == 3`);
            let z = proxy.getBuffer();
            pyodide.runPython(`assert getrefcount(${x}) == 4`);
            proxy.destroy();
            pyodide.runPython(`assert getrefcount(${x}) == 3`);
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
            pyodide.runPython(`assert getrefcount(${x}) == 2`);
            pyodide.runPython(`del ${x}`);
        }
        """
    )


def test_get_empty_buffer(selenium):
    """Previously empty buffers would raise alignment errors

    This is because when Python makes an empty buffer, apparently the pointer
    field is allowed to contain random garbage, which in particular won't be aligned.
    """
    selenium.run_js(
        """
        let a = pyodide.runPython(`
            from array import array
            array("Q")
        `);
        let b = a.getBuffer();
        b.release();
        a.destroy();
        """
    )


@pytest.mark.parametrize(
    "array_type",
    [
        ["i8", "Int8Array", "b"],
        ["u8", "Uint8Array", "B"],
        ["u8clamped", "Uint8ClampedArray", "B"],
        ["i16", "Int16Array", "h"],
        ["u16", "Uint16Array", "H"],
        ["i32", "Int32Array", "i"],
        ["u32", "Uint32Array", "I"],
        ["i64", "BigInt64Array", "q"],
        ["u64", "BigUint64Array", "Q"],
        ["f32", "Float32Array", "f"],
        ["f64", "Float64Array", "d"],
    ],
)
def test_pyproxy_get_buffer_type_argument(selenium, array_type):
    selenium.run_js(
        """
        self.a = pyodide.runPython("bytes(range(256))");
        assert(() => a instanceof pyodide.ffi.PyBuffer);
        """
    )
    try:
        mv = memoryview(bytes(range(256)))
        ty, array_ty, fmt = array_type
        [check, result] = selenium.run_js(
            f"""
            let buf = a.getBuffer({ty!r});
            assert(() => buf instanceof pyodide.ffi.PyBufferView);
            let check = (buf.data.constructor.name === {array_ty!r});
            let result = Array.from(buf.data);
            if(typeof result[0] === "bigint"){{
                result = result.map(x => x.toString(16));
            }}
            buf.release();
            return [check, result];
            """
        )
        assert check
        if fmt.lower() == "q":
            assert result == [hex(x).replace("0x", "") for x in list(mv.cast(fmt))]
        elif fmt == "f" or fmt == "d":
            from math import isclose, isnan

            for a, b in zip(result, list(mv.cast(fmt)), strict=False):
                if a and b and not (isnan(a) or isnan(b)):
                    assert isclose(a, b)
        else:
            assert result == list(mv.cast(fmt))
    finally:
        selenium.run_js("a.destroy(); self.a = undefined;")


def test_pyproxy_mixins(selenium):
    result = selenium.run_js(
        """
        let [noimpls, awaitable, iterable, iterator, awaititerable, awaititerator] = pyodide.runPython(`
            class NoImpls: pass

            class Await:
                def __await__(self):
                    return iter([])

            class Iter:
                def __iter__(self):
                    return iter([])

            class Next:
                def __next__(self):
                    pass

            class AwaitIter(Await, Iter): pass

            class AwaitNext(Await, Next): pass
            from pyodide.ffi import to_js
            to_js([NoImpls(), Await(), Iter(), Next(), AwaitIter(), AwaitNext()])
        `);
        let name_proxy = {noimpls, awaitable, iterable, iterator, awaititerable, awaititerator};
        let result = {};
        for(let [name, x] of Object.entries(name_proxy)){
            let impls = {};
            for(let [name, key] of [
                ["then", "then"],
                ["catch", "catch"],
                ["finally_", "finally"],
                ["iterable", Symbol.iterator],
                ["iterator", "next"],
            ]){
                impls[name] = key in x;
            }
            for(let name of ["PyAwaitable", "PyIterable", "PyIterator"]){
                impls[name] = x instanceof pyodide.ffi[name];
            }
            result[name] = impls;
            x.destroy();
        }
        return result;
        """
    )
    assert result == dict(
        noimpls=dict(
            then=False,
            catch=False,
            finally_=False,
            iterable=False,
            iterator=False,
        )
        | dict(PyAwaitable=False, PyIterable=False, PyIterator=False),
        awaitable=dict(
            then=True, catch=True, finally_=True, iterable=False, iterator=False
        )
        | dict(PyAwaitable=True, PyIterable=False, PyIterator=False),
        iterable=dict(
            then=False, catch=False, finally_=False, iterable=True, iterator=False
        )
        | dict(PyAwaitable=False, PyIterable=True, PyIterator=False),
        iterator=dict(
            then=False, catch=False, finally_=False, iterable=True, iterator=True
        )
        | dict(PyAwaitable=False, PyIterable=True, PyIterator=True),
        awaititerable=dict(
            then=True, catch=True, finally_=True, iterable=True, iterator=False
        )
        | dict(PyAwaitable=True, PyIterable=True, PyIterator=False),
        awaititerator=dict(
            then=True, catch=True, finally_=True, iterable=True, iterator=True
        )
        | dict(PyAwaitable=True, PyIterable=True, PyIterator=True),
    )


def test_pyproxy_mixins2(selenium):
    selenium.run_js(
        """
        let d = pyodide.runPython("{}");

        assert(() => !("prototype" in d));
        assert(() => !("caller" in d));
        assert(() => !("name" in d));
        assert(() => "length" in d);
        assert(() => d instanceof pyodide.ffi.PyDict);
        assert(() => d instanceof pyodide.ffi.PyProxyWithLength);
        assert(() => d instanceof pyodide.ffi.PyProxyWithHas);
        assert(() => d instanceof pyodide.ffi.PyProxyWithGet);
        assert(() => d instanceof pyodide.ffi.PyProxyWithSet);

        assert(() => "prototype" in d.__getitem__);
        assert(() => d.__getitem__.prototype === undefined);
        assert(() => !("length" in d.__getitem__));
        assert(() => !("name" in d.__getitem__));

        assert(() => d.$get.type === "builtin_function_or_method");
        assert(() => d.get.type === undefined);
        assert(() => d.set.type === undefined);
        d.destroy();
        """
    )


def test_pyproxy_mixins3(selenium):
    selenium.run_js(
        """
        let [Test, t] = pyodide.runPython(`
            class Test: pass
            from pyodide.ffi import to_js
            to_js([Test, Test()])
        `);
        assert(() => Test.prototype === undefined);
        assert(() => !("name" in Test));
        assert(() => !("length" in Test));

        assert(() => !("prototype" in t));
        assert(() => !("caller" in t));
        assert(() => !("name" in t));
        assert(() => !("length" in t));

        Test.prototype = 7;
        Test.name = 7;
        Test.length = 7;
        pyodide.runPython("assert Test.prototype == 7");
        pyodide.runPython("assert Test.name == 7");
        pyodide.runPython("assert Test.length == 7");
        delete Test.prototype;
        delete Test.name;
        delete Test.length;
        pyodide.runPython(`assert not hasattr(Test, "prototype")`);
        pyodide.runPython(`assert not hasattr(Test, "name")`);
        pyodide.runPython(`assert not hasattr(Test, "length")`);

        assertThrows( () => Test.$$ = 7, "TypeError", /^Cannot set read only field/);
        assertThrows( () => delete Test.$$, "TypeError", /^Cannot delete read only field/);
        Test.destroy();
        t.destroy();
        """
    )


def test_pyproxy_mixins41(selenium):
    selenium.run_js(
        """
        [Test, t] = pyodide.runPython(`
            class Test:
                caller="fifty"
                prototype="prototype"
                name="me"
                length=7
                def __call__(self, x):
                    return x + 1

            from pyodide.ffi import to_js
            to_js([Test, Test()])
        `);
        assert(() => Test.$prototype === "prototype");
        assert(() => Test.prototype === "prototype");
        assert(() => Test.name==="me");
        assert(() => Test.length === 7);

        assert(() => t.caller === "fifty");
        assert(() => "prototype" in t);
        assert(() => t.prototype === "prototype");
        assert(() => t.name==="me");
        assert(() => t.length === 7);
        assert(() => t(7) === 8);
        Test.destroy();
        t.destroy();
        """
    )


def test_pyproxy_mixins42(selenium):
    selenium.run_js(
        """
        let t = pyodide.runPython(`
            class Test:
                def __call__(self, x):
                    return x + 1

            from pyodide.ffi import to_js
            Test()
        `);
        assert(() => "prototype" in t);
        assert(() => t.prototype === undefined);
        t.destroy();
        """
    )


def test_pyproxy_mixins5(selenium):
    selenium.run_js(
        """
        [Test, t] = pyodide.runPython(`
            class Test:
                def __len__(self):
                    return 9
            from pyodide.ffi import to_js
            to_js([Test, Test()])
        `);
        assert(() => !("length" in Test));
        assert(() => t.length === 9);
        assert(() => t instanceof pyodide.ffi.PyProxyWithLength);
        t.length = 10;
        assert(() => t.$length === 10);
        let t__len__ = t.__len__;
        assert(() => t__len__() === 9);
        t__len__.destroy();
        Test.destroy();
        t.destroy();
        """
    )


def test_pyproxy_mixins6(selenium):
    selenium.run_js(
        """
        let l = pyodide.runPython(`
            l = [5, 6, 7] ; l
        `);
        assert(() => l.get.type === undefined);
        assert(() => l.get(1) === 6);
        assert(() => l.length === 3);
        assert(() => l instanceof pyodide.ffi.PyProxyWithLength);
        assert(() => l instanceof pyodide.ffi.PyProxyWithHas);
        assert(() => l instanceof pyodide.ffi.PyProxyWithGet);
        assert(() => l instanceof pyodide.ffi.PyProxyWithSet);
        l.set(0, 80);
        pyodide.runPython(`
            assert l[0] == 80
        `);
        l.delete(1);
        pyodide.runPython(`
            assert len(l) == 2 and l[1] == 7
        `);
        assert(() => l.length === 2 && l.get(1) === 7);
        l.destroy();
        """
    )


@pytest.mark.skip_pyproxy_check
def test_pyproxy_gc(selenium):
    if not hasattr(selenium, "collect_garbage"):
        pytest.skip("No gc exposed")

    # Two ways to trigger garbage collection in Chrome:
    # 1. options.add_argument("--js-flags=--expose-gc") in conftest, and use
    #    gc() in javascript.
    # 2. selenium.driver.execute_cdp_cmd("HeapProfiler.collectGarbage", {})
    #
    # Unclear how to trigger gc in Firefox. Possible to do this by navigating to
    # "about:memory" and then triggering a button press to the "GC" button, but
    # that seems too annoying.

    selenium.run_js(
        """
        self.x = new FinalizationRegistry((val) => { self.val = val; });
        x.register({}, 77);
        gc();
        """
    )
    time.sleep(0.1)
    selenium.run_js(
        """
        gc();
        """
    )
    assert selenium.run_js("return self.val;") == 77

    selenium.run_js(
        """
        self.res = new Map();

        let d = pyodide.runPython(`
            from js import res
            def get_ref_count(x):
                res[x] = sys.getrefcount(d)
                return res[x]

            import sys
            class Test:
                def __del__(self):
                    res["destructor_ran"] = True

                def get(self):
                    return 7

            d = Test()
            get_ref_count(0)
            d
        `);
        let get_ref_count = pyodide.globals.get("get_ref_count");
        get_ref_count(1);
        d.get();
        get_ref_count(2);
        d.get();
        d.destroy()
        """
    )
    selenium.collect_garbage()

    selenium.run(
        """
        get_ref_count(3)
        del d
        """
    )
    selenium.collect_garbage()
    a = selenium.run_js("return Array.from(res.entries());")
    assert dict(a) == {0: 2, 1: 3, 2: 4, 3: 2, "destructor_ran": True}


@pytest.mark.skip_pyproxy_check
def test_pyproxy_gc_destroy(selenium):
    if not hasattr(selenium, "collect_garbage"):
        pytest.skip("No gc exposed")

    selenium.run_js(
        """
        self.res = new Map();
        let d = pyodide.runPython(`
            from js import res
            def get_ref_count(x):
                res[x] = sys.getrefcount(d)
                return res[x]
            import sys
            class Test:
                def __del__(self):
                    res["destructor_ran"] = True

                def get(self):
                    return 7

            d = Test()
            get_ref_count(0)
            d
        `);
        let get_ref_count = pyodide.globals.get("get_ref_count");
        get_ref_count(1);
        d.get();
        get_ref_count(2);
        d.get();
        get_ref_count(3);
        delete d;
        get_ref_count.destroy();
        """
    )
    selenium.collect_garbage()
    selenium.collect_garbage()
    selenium.run(
        """
        get_ref_count(4)
        del d
        """
    )
    a = selenium.run_js("return Array.from(res.entries());")
    assert dict(a) == {
        0: 2,
        1: 3,
        2: 4,
        3: 4,
        4: 2,
        "destructor_ran": True,
    }


def test_pyproxy_implicit_copy(selenium):
    result = selenium.run_js(
        """
        let result = [];
        let a = pyodide.runPython(`d = { 1 : 2}; d`);
        let b = pyodide.runPython(`d`);
        result.push(a.get(1));
        result.push(b.get(1));
        a.destroy();
        b.destroy();
        return result;
        """
    )
    assert result[0] == 2
    assert result[1] == 2


@pytest.mark.skip_pyproxy_check
def test_errors(selenium):
    selenium.run_js(
        r"""
        let t = pyodide.runPython(`
            from pyodide.ffi import to_js
            def te(self, *args, **kwargs):
                raise Exception(repr(args))
            class Temp:
                __getattr__ = te
                __setattr__ = te
                __delattr__ = te
                __dir__ = te
                __call__ = te
                __getitem__ = te
                __setitem__ = te
                __delitem__ = te
                __iter__ = te
                __len__ = te
                __contains__ = te
                __await__ = te
                __repr__ = te
            to_js(Temp())
            Temp()
        `);
        assertThrows(() => t.x, "PythonError", "");
        try {
            t.x;
        } catch(e){
            assert(() => e instanceof pyodide.ffi.PythonError);
        }
        assertThrows(() => t.x = 2, "PythonError", "");
        assertThrows(() => delete t.x, "PythonError", "");
        assertThrows(() => Object.getOwnPropertyNames(t), "PythonError", "");
        assertThrows(() => t(), "PythonError", "");
        assertThrows(() => t.get(1), "PythonError", "");
        assertThrows(() => t.set(1, 2), "PythonError", "");
        assertThrows(() => t.delete(1), "PythonError", "");
        assertThrows(() => t.has(1), "PythonError", "");
        assertThrows(() => t.length, "PythonError", "");
        assertThrows(() => t.toString(), "PythonError", "");
        assertThrows(() => Array.from(t), "PythonError", "");
        await assertThrowsAsync(async () => await t, "PythonError", "");
        t.destroy();
        assertThrows(() => t.type, "Error",
            "Object has already been destroyed\n" +
            'The object was of type "Temp" and an error was raised when trying to generate its repr'
        );
        """
    )


@pytest.mark.skip_pyproxy_check
def test_nogil(selenium):
    selenium.run_js(
        r"""
        let t = pyodide.runPython(`
            def te(self, *args, **kwargs):
                raise Exception(repr(args))
            class Temp:
                __getattr__ = te
                __setattr__ = te
                __delattr__ = te
                __dir__ = te
                __call__ = te
                __getitem__ = te
                __setitem__ = te
                __delitem__ = te
                __iter__ = te
                __len__ = te
                __contains__ = te
                __await__ = te
                __repr__ = te
            Temp()
        `);
        // release GIL
        const tstate = pyodide._module._PyEval_SaveThread()

        assertThrows(() => t.x, "NoGilError", "");
        try {
            t.x;
        } catch(e){
            assert(() => e instanceof pyodide._api.NoGilError);
        }
        assertThrows(() => t.x = 2, "NoGilError", "");
        assertThrows(() => delete t.x, "NoGilError", "");
        assertThrows(() => Object.getOwnPropertyNames(t), "NoGilError", "");
        assertThrows(() => t(), "NoGilError", "");
        assertThrows(() => t.get(1), "NoGilError", "");
        assertThrows(() => t.set(1, 2), "NoGilError", "");
        assertThrows(() => t.delete(1), "NoGilError", "");
        assertThrows(() => t.has(1), "NoGilError", "");
        assertThrows(() => t.length, "NoGilError", "");
        assertThrows(() => t.toString(), "NoGilError", "");
        assertThrows(() => Array.from(t), "NoGilError", "");
        await assertThrowsAsync(async () => await t, "NoGilError", "");
        assertThrows(() => t.destroy(), "NoGilError", "");

        // acquire GIL
        pyodide._module._PyEval_RestoreThread(tstate)
        """
    )


@pytest.mark.skip_pyproxy_check
def test_fatal_error(selenium_standalone):
    """Inject fatal errors in all the reasonable entrypoints"""
    selenium_standalone.run_js(
        """
        let fatal_error = false;
        let old_fatal_error = pyodide._api.fatal_error;
        pyodide._api.fatal_error = (e) => {
            fatal_error = true;
            throw e;
        }
        try {
            function expect_fatal(func){
                fatal_error = false;
                try {
                    func();
                } catch(e) {
                    // pass
                } finally {
                    if(!fatal_error){
                        throw new Error(`No fatal error occurred: ${func.toString().slice(6)}`);
                    }
                }
            }
            let t = pyodide.runPython(`
                from _pyodide_core import trigger_fatal_error
                def tfe(*args, **kwargs):
                    trigger_fatal_error()
                class Temp:
                    __getattr__ = tfe
                    __setattr__ = tfe
                    __delattr__ = tfe
                    __dir__ = tfe
                    __call__ = tfe
                    __getitem__ = tfe
                    __setitem__ = tfe
                    __delitem__ = tfe
                    __iter__ = tfe
                    __len__ = tfe
                    __contains__ = tfe
                    __await__ = tfe
                    __repr__ = tfe
                    __del__ = tfe
                Temp()
            `);
            expect_fatal(() => "x" in t);
            expect_fatal(() => t.x);
            expect_fatal(() => t.x = 2);
            expect_fatal(() => delete t.x);
            expect_fatal(() => Object.getOwnPropertyNames(t));
            expect_fatal(() => t());
            expect_fatal(() => t.get(1));
            expect_fatal(() => t.set(1, 2));
            expect_fatal(() => t.delete(1));
            expect_fatal(() => t.has(1));
            expect_fatal(() => t.length);
            expect_fatal(() => t.toString());
            expect_fatal(() => Array.from(t));
            t.destroy();
            /*
            // FIXME: Test `memory access out of bounds` error.
            //        Testing this causes trouble on Chrome 97.0.4692.99 / ChromeDriver 97.0.4692.71.
            //        (See: https://github.com/pyodide/pyodide/pull/2152)
            a = pyodide.runPython(`
                from array import array
                array("I", [1,2,3,4])
            `);
            b = a.getBuffer();
            b._view_ptr = 1e10;
            expect_fatal(() => b.release());
            */
        } finally {
            pyodide._api.fatal_error = old_fatal_error;
        }
        """
    )


def test_pyproxy_call(selenium):
    selenium.run_js(
        """
        pyodide.runPython(`
            from pyodide.ffi import to_js
            def f(x=2, y=3):
                return to_js([x, y])
        `);
        self.f = pyodide.globals.get("f");
        """
    )

    def assert_call(s, val):
        res = selenium.run_js(f"return {s};")
        assert res == val

    assert_call("f()", [2, 3])
    assert_call("f(7)", [7, 3])
    assert_call("f(7, -1)", [7, -1])

    assert_call("f.callKwargs({})", [2, 3])
    assert_call("f.callKwargs(7, {})", [7, 3])
    assert_call("f.callKwargs(7, -1, {})", [7, -1])
    assert_call("f.callKwargs({ y : 4 })", [2, 4])
    assert_call("f.callKwargs({ y : 4, x : 9 })", [9, 4])
    assert_call("f.callKwargs(8, { y : 4 })", [8, 4])

    msg = "TypeError: callKwargs requires at least one argument"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js("f.callKwargs()")

    msg = "TypeError: callKwargs requires at least one argument"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js("f.callKwargs()")

    msg = r"TypeError: f\(\) got an unexpected keyword argument 'z'"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js("f.callKwargs({z : 6})")

    msg = r"TypeError: f\(\) got multiple values for argument 'x'"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js("f.callKwargs(76, {x : 6})")

    selenium.run_js("f.destroy()")


def test_pyproxy_borrow(selenium):
    selenium.run_js(
        """
        let t = pyodide.runPython(`
            class Tinner:
                def f(self):
                    return 7
            class Touter:
                T = Tinner()
            Touter
        `);
        assert(() => t.T.f() === 7);
        let T = t.T;
        let Tcopy = T.copy();
        assert(() => T.f() === 7);
        assert(() => Tcopy.f() === 7);
        t.destroy();
        assert(() => Tcopy.f() === 7);
        assertThrows(() => T.f(), "Error", "automatically destroyed in the process of destroying the proxy it was borrowed from");
        Tcopy.destroy();
        """
    )


def test_coroutine_scheduling(selenium):
    selenium.run_js(
        """
        let f = pyodide.runPython(`
            x = 0
            async def f():
                global x
                print('hi!')
                x += 1
            f
        `);
        setTimeout(f, 100);
        await sleep(200);
        assert(() => pyodide.globals.get('x') === 1);
        f.destroy();
        """
    )


def test_pyproxy_apply(selenium):
    # Try to match behavior of real .apply
    selenium.run_js(
        """
        pyodide.runPython(`
            from pyodide.ffi import to_js
            def f(*args):
                return to_js(args)
        `);
        let fpy = pyodide.globals.get("f");
        let fjs = function(...args){ return args; };
        let examples = [
            undefined,
            null,
            {},
            {0:1, 1:7, 2: -3},
            { *[Symbol.iterator](){yield 3; yield 5; yield 7;} },
            {0:1, 1:7, 2: -3, length: 2},
            [1,7,9,5],
            function(a,b,c){},
        ];
        for(let input of examples){
            assert(() => JSON.stringify(fpy.apply(undefined, input)) === JSON.stringify(fjs.apply(undefined, input)));
        }

        for(let error_input of [1, "abc", 1n, Symbol.iterator, true]) {
            assertThrows(() => fjs.apply(undefined, error_input), "TypeError", "");
            assertThrows(() => fpy.apply(undefined, error_input), "TypeError", "");
        }

        fpy.destroy();
        """
    )


def test_pyproxy_this1(selenium):
    selenium.run_js(
        """
        let f = pyodide.runPython(`
            x = 0
            def f(self, x):
                return getattr(self, x)
            f
        `);

        let x = {};
        x.f = f.captureThis();
        x.a = 7;
        assert(() => x.f("a") === 7 );
        f.destroy();
        """
    )


def test_pyproxy_this2(selenium):
    selenium.run_js(
        """
        let g = pyodide.runPython(`
            x = 0
            from pyodide.ffi import to_js
            def f(*args):
                return to_js(args)
            f
        `);

        let f = g.captureThis();
        let fjs = function(...args){return [this, ...args];};

        let f1 = f.bind(1);
        let fjs1 = fjs.bind(1);
        assert(() => JSON.stringify(f1(2, 3, 4)) === JSON.stringify(fjs1(2, 3, 4)));

        let f2 = f1.bind(2);
        let fjs2 = fjs1.bind(2);
        assert(() => JSON.stringify(f2(2, 3, 4)) === JSON.stringify(fjs2(2, 3, 4)));
        let f3 = f.bind(2);
        let fjs3 = fjs.bind(2);
        assert(() => JSON.stringify(f3(2, 3, 4)) === JSON.stringify(fjs3(2, 3, 4)));

        let gjs = function(...args){return [...args];};

        let g1 = g.bind(1, 2, 3, 4);
        let gjs1 = gjs.bind(1, 2, 3, 4);

        let g2 = g1.bind(5, 6, 7, 8);
        let gjs2 = gjs1.bind(5, 6, 7, 8);

        let g3 = g2.captureThis();

        assert(() => JSON.stringify(g1(-1, -2, -3, -4)) === JSON.stringify(gjs1(-1, -2, -3, -4)));
        assert(() => JSON.stringify(g2(-1, -2, -3, -4)) === JSON.stringify(gjs2(-1, -2, -3, -4)));
        assert(() => JSON.stringify(g3(-1, -2, -3, -4)) === JSON.stringify([1, 2, 3, 4, 6, 7, 8, -1, -2, -3, -4]));
        g.destroy();
        """
    )


@run_in_pyodide
async def test_async_iter1(selenium):
    from pyodide.code import run_js

    class Gen:
        async def __aiter__(self):
            yield 1
            yield 2

    g = Gen()

    p = run_js(
        """
        async (g) => {
            assert(() => g instanceof pyodide.ffi.PyAsyncIterable);
            let r = [];
            for await (let a of g) {
                r.push(a);
            }
            return r;
        }
    """
    )(g)

    assert (await p).to_py() == [1, 2]


@run_in_pyodide
async def test_async_iter2(selenium):
    from pyodide.code import run_js

    class Gen:
        def __init__(self):
            self.i = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            self.i += 1
            if self.i > 2:
                raise StopAsyncIteration
            return self.i

    g = Gen()

    p = run_js(
        """
        async (g) => {
            assert(() => g instanceof pyodide.ffi.PyAsyncIterable);
            let r = [];
            for await (let a of g) {
                r.push(a);
            }
            return r;
        }
    """
    )(g)

    assert (await p).to_py() == [1, 2]


@run_in_pyodide
def test_gen(selenium):
    from pyodide.code import run_js

    def g():
        n = 0
        for _ in range(3):
            n = yield n + 2

    p = run_js(
        """
        (g) => {
            assert(() => g instanceof pyodide.ffi.PyGenerator);
            assert(() => g instanceof pyodide.ffi.PyIterable);
            assert(() => g instanceof pyodide.ffi.PyIterator);
            assert(() => !(g instanceof pyodide.ffi.PyAsyncGenerator));
            let r = [];
            r.push(g.next());
            r.push(g.next(3));
            r.push(g.next(4));
            r.push(g.next(5));
            return r;
        }
    """
    )(g())

    assert p.to_py() == [
        {"done": False, "value": 2},
        {"done": False, "value": 5},
        {"done": False, "value": 6},
        {"done": True, "value": None},
    ]


@run_in_pyodide
def test_gen_return(selenium):
    from pyodide.code import run_js

    def g1():
        yield 1
        yield 2

    p = run_js(
        """
        (g) => {
            let r = [];
            r.push(g.next());
            r.push(g.return(5));
            return r;
        }
    """
    )(g1())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": 5}]

    def g2():
        try:
            yield 1
            yield 2
        finally:
            yield 3  # noqa: B901
            return 5  # noqa: B012, B901

    p = run_js(
        """
        (g) => {
            let r = [];
            r.push(g.next());
            r.push(g.return(5));
            r.push(g.next());
            return r;
        }
    """
    )(g2())
    assert p.to_py() == [
        {"done": False, "value": 1},
        {"done": False, "value": 3},
        {"done": True, "value": 5},
    ]

    def g3():
        try:
            yield 1
            yield 2
        finally:
            return 3  # noqa: B901, B012

    p = run_js(
        """
        (g) => {
            let r = [];
            r.push(g.next());
            r.push(g.return(5));
            return r;
        }
    """
    )(g3())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": 3}]


@run_in_pyodide
def test_gen_throw(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException

    def g1():
        yield 1
        yield 2

    p = run_js(
        """
        (g) => {
            g.next();
            g.throw(new TypeError('hi'));
        }
    """
    )
    with pytest.raises(JsException, match="hi"):
        p(g1())

    def g2():
        try:
            yield 1
            yield 2
        finally:
            yield 3
            return 5  # noqa: B901, B012

    p = run_js(
        """
        (g) => {
            let r = [];
            r.push(g.next());
            r.push(g.throw(new TypeError('hi')));
            r.push(g.next());
            return r;
        }
    """
    )(g2())
    assert p.to_py() == [
        {"done": False, "value": 1},
        {"done": False, "value": 3},
        {"done": True, "value": 5},
    ]

    def g3():
        try:
            yield 1
            yield 2
        finally:
            return 3  # noqa: B901, B012

    p = run_js(
        """
        (g) => {
            let r = [];
            r.push(g.next());
            r.push(g.throw(new TypeError('hi')));
            return r;
        }
    """
    )(g3())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": 3}]


@run_in_pyodide
async def test_async_gen1(selenium):
    from pyodide.code import run_js

    async def g():
        n = 0
        for _ in range(3):
            n = yield n + 2

    p = run_js(
        """
        async (g) => {
            assert(() => g instanceof pyodide.ffi.PyAsyncGenerator);
            assert(() => g instanceof pyodide.ffi.PyAsyncIterable);
            assert(() => g instanceof pyodide.ffi.PyAsyncIterator);
            assert(() => !(g instanceof pyodide.ffi.PyGenerator));
            let r = [];
            r.push(await g.next());
            r.push(await g.next(3));
            r.push(await g.next(4));
            r.push(await g.next(5));
            return r;
        }
    """
    )(g())

    assert (await p).to_py() == [
        {"done": False, "value": 2},
        {"done": False, "value": 5},
        {"done": False, "value": 6},
        {"done": True, "value": None},
    ]


@run_in_pyodide
async def test_async_gen2(selenium):
    from pyodide.code import run_js

    async def g():
        for n in range(3):
            yield n

    p = run_js(
        """
        async (g) => {
            let result = [];
            for await (let x of g){
                result.push(x);
            }
            return result;
        }
    """
    )(g())
    assert (await p).to_py() == [0, 1, 2]


@run_in_pyodide
async def test_async_gen_return(selenium):
    from pyodide.code import run_js

    async def g1():
        yield 1
        yield 2

    p = await run_js(
        """
        async (g) => {
            let r = [];
            r.push(await g.next());
            r.push(await g.return(5));
            return r;
        }
    """
    )(g1())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": 5}]

    async def g2():
        try:
            yield 1
            yield 2
        finally:
            yield 3  # noqa: B901
            return  # noqa: B012, B901

    p = await run_js(
        """
        async (g) => {
            let r = [];
            r.push(await g.next());
            r.push(await g.return(5));
            r.push(await g.next());
            return r;
        }
    """
    )(g2())
    assert p.to_py() == [
        {"done": False, "value": 1},
        {"done": False, "value": 3},
        {"done": True, "value": None},
    ]

    async def g3():
        try:
            yield 1
            yield 2
        finally:
            return  # noqa: B901, B012

    p = await run_js(
        """
        async (g) => {
            let r = [];
            r.push(await g.next());
            r.push(await g.return(5));
            return r;
        }
    """
    )(g3())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": None}]


@run_in_pyodide
async def test_async_gen_throw(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException

    async def g1():
        yield 1
        yield 2

    p = run_js(
        """
        async (g) => {
            await g.next();
            await g.throw(new TypeError('hi'));
        }
    """
    )
    with pytest.raises(JsException, match="hi"):
        await p(g1())

    async def g2():
        try:
            yield 1
            yield 2
        finally:
            yield 3
            return  # noqa: B901, B012

    p = await run_js(
        """
        async (g) => {
            let r = [];
            r.push(await g.next());
            r.push(await g.throw(new TypeError('hi')));
            r.push(await g.next());
            return r;
        }
    """
    )(g2())
    assert p.to_py() == [
        {"done": False, "value": 1},
        {"done": False, "value": 3},
        {"done": True, "value": None},
    ]

    async def g3():
        try:
            yield 1
            yield 2
        finally:
            return  # noqa: B901, B012

    p = await run_js(
        """
        async (g) => {
            let r = [];
            r.push(await g.next());
            r.push(await g.throw(new TypeError('hi')));
            return r;
        }
    """
    )(g3())
    assert p.to_py() == [{"done": False, "value": 1}, {"done": True, "value": None}]


@run_in_pyodide
def test_roundtrip_no_destroy(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import create_proxy

    def isalive(p):
        return getattr(p, "$$").ptr != 0

    p = create_proxy({1: 2})
    run_js("(x) => x")(p)
    assert isalive(p)
    run_js(
        """
    (p) => {
        p.destroy({destroyRoundtrip : false});
    }
    """
    )(p)
    assert isalive(p)
    run_js(
        """
    (p) => {
        p.destroy({destroyRoundtrip : true});
    }
    """
    )(p)
    assert not isalive(p)
    p = create_proxy({1: 2})
    run_js(
        """
    (p) => {
        p.destroy();
    }
    """
    )(p)
    assert not isalive(p)


@run_in_pyodide
async def test_multiple_interpreters(selenium):
    from js import loadPyodide  # type:ignore[attr-defined]

    py2 = await loadPyodide()
    d1 = {"a": 2}
    d2 = py2.runPython(str(d1))
    assert d2.toJs().to_py() == d1


@run_in_pyodide
def test_pyproxy_of_list_index(selenium):
    from pyodide.code import run_js

    pylist = [9, 8, 7]
    jslist = run_js(
        """
        (p) => {
            return [p[0], p[1], p[2]]
        }
        """
    )(pylist)
    assert jslist.to_py() == pylist


@run_in_pyodide
def test_pyproxy_of_list_join(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["Wind", "Water", "Fire"]
    ajs = to_js(a)
    func = run_js("((a, k) => a.join(k))")

    assert func(a, None) == func(ajs, None)
    assert func(a, ", ") == func(ajs, ", ")
    assert func(a, " ") == func(ajs, " ")


@run_in_pyodide
def test_pyproxy_of_list_slice(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["ant", "bison", "camel", "duck", "elephant"]
    ajs = to_js(a)

    func_strs = [
        "a.slice(2)",
        "a.slice(2, 4)",
        "a.slice(1, 5)",
        "a.slice(-2)",
        "a.slice(2, -1)",
        "a.slice()",
    ]
    for func_str in func_strs:
        func = run_js(f"(a) => {func_str}")
        assert func(a).to_py() == func(ajs).to_py()


@run_in_pyodide
def test_pyproxy_of_list_indexOf(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["ant", "bison", "camel", "duck", "bison"]
    ajs = to_js(a)

    func_strs = [
        "beasts.indexOf('bison')",
        "beasts.indexOf('bison', 2)",
        "beasts.indexOf('bison', -4)",
        "beasts.indexOf('bison', 3)",
        "beasts.indexOf('giraffe')",
    ]
    for func_str in func_strs:
        func = run_js(f"(beasts) => {func_str}")
        assert func(a) == func(ajs)


@run_in_pyodide
def test_pyproxy_of_list_lastIndexOf(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["ant", "bison", "camel", "duck", "bison"]
    ajs = to_js(a)

    func_strs = [
        "beasts.lastIndexOf('bison')",
        "beasts.lastIndexOf('bison', 2)",
        "beasts.lastIndexOf('bison', -4)",
        "beasts.lastIndexOf('bison', 3)",
        "beasts.lastIndexOf('giraffe')",
    ]
    for func_str in func_strs:
        func = run_js(f"(beasts) => {func_str}")
        assert func(a) == func(ajs)


@run_in_pyodide
def test_pyproxy_of_list_forEach(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["a", "b", "c"]
    ajs = to_js(a)

    func = run_js(
        """
        ((a) => {
            let s = "";
            a.forEach((elt, idx, list) => {
                s += "::";
                s += idx;
                s += elt;
                s += this[elt];
            },
                {a: 6, b: 9, c: 22}
            );
            return s;
        })
        """
    )

    assert func(a) == func(ajs)


@run_in_pyodide
def test_pyproxy_of_list_map(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["a", "b", "c"]
    ajs = to_js(a)
    func = run_js(
        """
        (a) => a.map(
            function (elt, idx, list){
                return [elt, idx, this[elt]]
            },
            {a: 6, b: 9, c: 22}
        )
        """
    )
    assert func(a).to_py() == func(ajs).to_py()


@run_in_pyodide
def test_pyproxy_of_list_filter(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = list(range(20, 0, -2))
    ajs = to_js(a)
    func = run_js(
        """
        (a) => a.filter(
            function (elt, idx){
                return elt + idx > 12
            }
        )
        """
    )
    assert func(a).to_py() == func(ajs).to_py()


@run_in_pyodide
def test_pyproxy_of_list_reduce(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = list(range(20, 0, -2))
    ajs = to_js(a)
    func = run_js(
        """
        (a) => a.reduce((l, r) => l + 2*r)
        """
    )
    assert func(a) == func(ajs)


@run_in_pyodide
def test_pyproxy_of_list_reduceRight(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = list(range(20, 0, -2))
    ajs = to_js(a)
    func = run_js(
        """
        (a) => a.reduceRight((l, r) => l + 2*r)
        """
    )
    assert func(a) == func(ajs)


@run_in_pyodide
def test_pyproxy_of_list_some(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    func = run_js("(a) => a.some((element, idx) => (element + idx) % 2 === 0)")
    for a in [
        [1, 2, 3, 4, 5],
        [2, 3, 4, 5],
        [1, 3, 5],
        [1, 4, 5],
        [4, 5],
    ]:
        assert func(a) == func(to_js(a))


@run_in_pyodide
def test_pyproxy_of_list_every(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    func = run_js("(a) => a.every((element, idx) => (element + idx) % 2 === 0)")
    for a in [
        [1, 2, 3, 4, 5],
        [2, 3, 4, 5],
        [1, 3, 5],
        [1, 4, 5],
        [4, 5],
    ]:
        assert func(a) == func(to_js(a))


@run_in_pyodide
def test_pyproxy_of_list_at(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [5, 12, 8, 130, 44]
    ajs = to_js(a)

    func = run_js("(a, idx) => a.at(idx)")
    for idx in [2, 3, 4, -2, -3, -4, 5, 7, -7]:
        assert func(a, idx) == func(ajs, idx)


@run_in_pyodide
def test_pyproxy_of_list_concat(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [[5, 12, 8], [130, 44], [6, 7, 7]]
    ajs = to_js(a)

    func = run_js("(a, b, c) => a.concat(b, c)")
    assert func(*a).to_py() == func(*ajs).to_py()


@run_in_pyodide
def test_pyproxy_of_list_includes(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [5, 12, 8, 130, 44, 6, 7, 7]
    ajs = to_js(a)

    func = run_js("(a, n) => a.includes(n)")
    for n in range(4, 10):
        assert func(a, n) == func(ajs, n)


@run_in_pyodide
def test_pyproxy_of_list_entries(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [5, 12, 8, 130, 44, 6, 7, 7]
    ajs = to_js(a)

    func = run_js("(a, k) => Array.from(a[k]())")
    for k in ["entries", "keys", "values"]:
        assert func(a, k).to_py() == func(ajs, k).to_py()


@run_in_pyodide
def test_pyproxy_of_list_find(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [5, 12, 8, 130, 44, 6, 7, 7]
    ajs = to_js(a)

    func = run_js("(a, k) => a[k](element => element > 10)")
    for k in ["find", "findIndex"]:
        assert func(a, k) == func(ajs, k)


@run_in_pyodide
def test_pyproxy_of_list_sort(selenium):
    # from
    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/sort#creating_displaying_and_sorting_an_array
    # Yes, JavaScript sort is weird.
    from pyodide.code import run_js

    stringArray = ["Blue", "Humpback", "Beluga"]
    numberArray = [40, None, 1, 5, 200]
    numericStringArray = ["80", "9", "700"]
    mixedNumericArray = ["80", "9", "700", 40, 1, 5, 200]

    run_js("globalThis.compareNumbers = (a, b) => a - b")

    assert run_js("((a) => a.join())")(stringArray) == "Blue,Humpback,Beluga"
    assert run_js("((a) => a.sort())")(stringArray) is stringArray
    assert stringArray == ["Beluga", "Blue", "Humpback"]

    assert run_js("((a) => a.join())")(numberArray) == "40,,1,5,200"
    assert run_js("((a) => a.sort())")(numberArray) == [1, 200, 40, 5, None]
    assert run_js("((a) => a.sort(compareNumbers))")(numberArray) == [
        1,
        5,
        40,
        200,
        None,
    ]

    assert run_js("((a) => a.join())")(numericStringArray) == "80,9,700"
    assert run_js("((a) => a.sort())")(numericStringArray) == ["700", "80", "9"]
    assert run_js("((a) => a.sort(compareNumbers))")(numericStringArray) == [
        "9",
        "80",
        "700",
    ]

    assert run_js("((a) => a.join())")(mixedNumericArray) == "80,9,700,40,1,5,200"
    assert run_js("((a) => a.sort())")(mixedNumericArray) == [
        1,
        200,
        40,
        5,
        "700",
        "80",
        "9",
    ]
    assert run_js("((a) => a.sort(compareNumbers))")(mixedNumericArray) == [
        1,
        5,
        "9",
        40,
        "80",
        200,
        "700",
    ]


@run_in_pyodide
def test_pyproxy_of_list_reverse(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [3, 2, 4, 1, 5]
    ajs = to_js(a)

    func = run_js("((a) => a.reverse())")
    assert func(a) is a
    func(ajs)
    assert ajs.to_py() == a


@pytest.mark.parametrize(
    "func",
    [
        'splice(2, 0, "drum")',
        'splice(2, 0, "drum", "guitar")',
        "splice(3, 1)",
        'splice(2, 1, "trumpet")',
        'splice(0, 2, "parrot", "anemone", "blue")',
        "splice(2, 2)",
        "splice(-2, 1)",
        "splice(2)",
        "splice()",
    ],
)
@run_in_pyodide
def test_pyproxy_of_list_splice(selenium, func):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["angel", "clown", "mandarin", "sturgeon"]
    ajs = to_js(a)

    func = run_js(f"((a) => a.{func})")
    assert func(a).to_py() == func(ajs).to_py()
    assert a == ajs.to_py()


@run_in_pyodide
def test_pyproxy_of_list_push(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [4, 5, 6]
    ajs = to_js(a)

    func = run_js("(a) => a.push(1, 2, 3)")
    assert func(a) == func(ajs)
    assert ajs.to_py() == a

    a = [4, 5, 6]
    ajs = to_js(a)
    func = run_js(
        """
        (a) => {
            a.push(1);
            a.push(2);
            return a.push(3);
        }
        """
    )
    assert func(a) == func(ajs)
    assert ajs.to_py() == a


@run_in_pyodide
def test_pyproxy_of_list_pop(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    func = run_js("((a) => a.pop())")

    for a in [
        [],
        ["broccoli", "cauliflower", "cabbage", "kale", "tomato"],
    ]:
        ajs = to_js(a)
        assert func(a) == func(ajs)
        assert ajs.to_py() == a


@run_in_pyodide
def test_pyproxy_of_list_shift(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["Andrew", "Tyrone", "Paul", "Maria", "Gayatri"]
    ajs = to_js(a)

    func = run_js(
        """
        (a) => {
            let result = [];
            while (typeof (i = a.shift()) !== "undefined") {
                result.push(i);
            }
            return result;
        }
        """
    )
    assert func(a).to_py() == func(ajs).to_py()
    assert a == []
    assert ajs.to_py() == []


@run_in_pyodide
def test_pyproxy_of_list_unshift(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = [4, 5, 6]
    ajs = to_js(a)

    func = run_js("(a) => a.unshift(1, 2, 3)")
    assert func(a) == func(ajs)
    assert ajs.to_py() == a

    a = [4, 5, 6]
    ajs = to_js(a)
    func = run_js(
        """
        (a) => {
            a.unshift(1);
            a.unshift(2);
            return a.unshift(3);
        }
        """
    )
    assert func(a) == func(ajs)
    assert ajs.to_py() == a


@pytest.mark.parametrize(
    "func",
    [
        "copyWithin(-2)",
        "copyWithin(0, 3)",
        "copyWithin(0, 3, 4)",
        "copyWithin(-2, -3, -1)",
    ],
)
@run_in_pyodide
def test_pyproxy_of_list_copyWithin(selenium, func):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["a", "b", "c", "d", "e"]
    ajs = to_js(a)
    func = run_js(f"(a) => a.{func}")
    assert func(a) is a
    func(ajs)
    assert a == ajs.to_py()


@pytest.mark.parametrize(
    "func",
    [
        "fill(0, 2, 4)",
        "fill(5, 1)",
        "fill(6)",
    ],
)
@run_in_pyodide
def test_pyproxy_of_list_fill(selenium, func):
    from pyodide.code import run_js
    from pyodide.ffi import to_js

    a = ["a", "b", "c", "d", "e"]
    ajs = to_js(a)
    func = run_js(f"(a) => a.{func}")
    assert func(a) is a
    func(ajs)
    assert a == ajs.to_py()


def test_pyproxy_instanceof_function(selenium):
    weird_function_shim = ""
    if selenium.browser in ["firefox", "node"]:
        # A hack to make the test work: In node and firefox this test fails. But
        # I can't reproduce the failure in a normal browser / outside of the
        # test suite. The trouble seems to be that the value of
        # `globalThis.Function` changes its identity from when we define
        # `PyProxyFunction` to when we execute this test. So we store `Function`
        # on `pyodide._api.tests` so we can retrieve the original value of it
        # for the test. This is nonsense but because the failure only occurs in
        # the test suite and not in real life I guess it's okay????
        # Also, no clue how node and firefox are affected but not Chrome.
        weird_function_shim = "let Function = pyodide._api.tests.Function;"

    selenium.run_js(
        f"""
        {weird_function_shim}
        """
        """
        const pyFunc_0 = pyodide.runPython(`
            lambda: print("zero")
        `);

        const pyFunc_1 = pyodide.runPython(`
            def foo():
                print("two")
            foo
        `);

        const pyFunc_2 = pyodide.runPython(`
            class A():
                def a(self):
                    print("three") # method from class
            A.a
        `);

        const pyFunc_3 = pyodide.runPython(`
            class B():
                def __call__(self):
                    print("five (B as a callable instance)")

            b = B()
            b
        `);

        assert(() => pyFunc_0 instanceof Function);
        assert(() => pyFunc_0 instanceof pyodide.ffi.PyProxy);
        assert(() => pyFunc_0 instanceof pyodide.ffi.PyCallable);

        assert(() => pyFunc_1 instanceof Function);
        assert(() => pyFunc_1 instanceof pyodide.ffi.PyProxy);
        assert(() => pyFunc_1 instanceof pyodide.ffi.PyCallable);

        assert(() => pyFunc_2 instanceof Function);
        assert(() => pyFunc_2 instanceof pyodide.ffi.PyProxy);
        assert(() => pyFunc_2 instanceof pyodide.ffi.PyCallable);

        assert(() => pyFunc_3 instanceof Function);
        assert(() => pyFunc_3 instanceof pyodide.ffi.PyProxy);
        assert(() => pyFunc_3 instanceof pyodide.ffi.PyCallable);

        d = pyodide.runPython("{}");
        assert(() => !(d instanceof Function));
        assert(() => !(d instanceof pyodide.ffi.PyCallable));
        assert(() => d instanceof pyodide.ffi.PyProxy);
        assert(() => d instanceof pyFunc_0.constructor);
        assert(() => pyFunc_0 instanceof d.constructor);

        for(const p of [pyFunc_0, pyFunc_1, pyFunc_2, pyFunc_3, d])  {
            p.destroy();
        }
        """
    )


def test_pyproxy_callable_prototype(selenium):
    result = selenium.run_js(
        """
        const o = pyodide.runPython("lambda:None");
        const res = Object.fromEntries(Reflect.ownKeys(Function.prototype).map(k => [k.toString(), k in o]));
        o.destroy();
        return res;
        """
    )
    subdict = {
        "length": False,
        "name": False,
        "arguments": False,
        "caller": False,
        "apply": True,
        "bind": True,
        "call": True,
        "Symbol(Symbol.hasInstance)": True,
    }
    filtered_result = {k: v for (k, v) in result.items() if k in subdict}
    assert filtered_result == subdict
