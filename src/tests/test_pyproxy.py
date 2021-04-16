# See also test_typeconversions, and test_python.
import pytest


def test_pyproxy(selenium):
    selenium.run(
        """
        class Foo:
          bar = 42
          def get_value(self, value):
            return value * 64
        f = Foo()
        """
    )
    selenium.run_js("window.f = pyodide.globals.get('f')")
    assert selenium.run_js("return f.type") == "Foo"
    assert selenium.run_js("return f.get_value(2)") == 128
    assert selenium.run_js("return f.bar") == 42
    assert selenium.run_js("return ('bar' in f)")
    selenium.run_js("f.baz = 32")
    assert selenium.run("f.baz") == 32
    assert set(selenium.run_js("return Object.getOwnPropertyNames(f)")) > set(
        [
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
        ]
    )
    assert selenium.run("hasattr(f, 'baz')")
    selenium.run_js("delete pyodide.globals.get('f').baz")
    assert not selenium.run("hasattr(f, 'baz')")
    assert selenium.run_js("return pyodide.globals.get('f').toString()").startswith(
        "<Foo"
    )


def test_pyproxy_refcount(selenium):
    result = selenium.run_js(
        """
        function getRefCount(){
            return pyodide.runPython("sys.getrefcount(pyfunc)");
        }
        let result = [];
        window.jsfunc = function (f) { f(); };
        pyodide.runPython(`
            import sys
            from js import window

            def pyfunc(*args, **kwargs):
                print(*args, **kwargs)
        `);

        // the refcount should be 2 because:
        //
        // 1. pyfunc exists
        // 2. pyfunc is referenced from the sys.getrefcount()-test below

        result.push([getRefCount(), 2]);

        // the refcount should be 3 because:
        //
        // 1. pyfunc exists
        // 2. one reference from PyProxy to pyfunc is alive
        // 3. pyfunc is referenced from the sys.getrefcount()-test below

        pyodide.runPython(`
            window.jsfunc(pyfunc) # creates new PyProxy
        `);

        result.push([getRefCount(), 3])
        pyodide.runPython(`
            window.jsfunc(pyfunc) # re-used existing PyProxy
            window.jsfunc(pyfunc) # re-used existing PyProxy
        `)

        // the refcount should be 3 because:
        //
        // 1. pyfunc exists
        // 2. one reference from PyProxy to pyfunc is alive
        // 3. pyfunc is referenced from the sys.getrefcount()-test
        result.push([getRefCount(), 3]);
        return result;
        """
    )
    for [a, b] in result:
        assert a == b, result


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
    msg = "Object has already been destroyed"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run_js(
            """
            let f = pyodide.globals.get('f');
            console.assert(f.get_value(1) === 64);
            f.destroy();
            f.get_value();
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
        return [c.type, [...c]];
        """
    )
    assert ty == "generator"
    assert l == list(range(10))

    [ty, l] = selenium.run_js(
        """
        c = pyodide.runPython(`
            from collections import ChainMap
            ChainMap({"a" : 2, "b" : 3})
        `);
        return [c.type, [...c]];
        """
    )
    assert ty == "ChainMap"
    assert set(l) == set(["a", "b"])

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
        window.a = pyodide.runPython("bytes(range(256))");
        """
    )
    try:
        mv = memoryview(bytes(range(256)))
        ty, array_ty, fmt = array_type
        [check, result] = selenium.run_js(
            f"""
            let buf = a.getBuffer({ty!r});
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
            from math import isclose

            for a, b in zip(result, list(mv.cast(fmt))):
                if a and b:
                    assert isclose(a, b)
        else:
            assert result == list(mv.cast(fmt))
    finally:
        selenium.run_js("a.destroy(); window.a = undefined;")


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

            [NoImpls(), Await(), Iter(), Next(), AwaitIter(), AwaitNext()]
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
            result[name] = impls;
        }
        return result;
        """
    )
    assert result == dict(
        noimpls=dict(
            then=False, catch=False, finally_=False, iterable=False, iterator=False
        ),
        awaitable=dict(
            then=True, catch=True, finally_=True, iterable=False, iterator=False
        ),
        iterable=dict(
            then=False, catch=False, finally_=False, iterable=True, iterator=False
        ),
        iterator=dict(
            then=False, catch=False, finally_=False, iterable=True, iterator=True
        ),
        awaititerable=dict(
            then=True, catch=True, finally_=True, iterable=True, iterator=False
        ),
        awaititerator=dict(
            then=True, catch=True, finally_=True, iterable=True, iterator=True
        ),
    )


def test_pyproxy_mixins2(selenium):
    selenium.run_js(
        """
        window.assert = function assert(cb){
            if(cb() !== true){
                throw new Error(`Assertion failed: ${cb.toString().slice(6)}`);
            }
        };
        window.assertThrows = function assert(cb, errname, pattern){
          let err = undefined;
          try {
            cb();
          } catch(e) {
            err = e;
          } finally {
            if(!err){
              throw new Error(`assertThrows(${cb.toString()}) failed, no error thrown`);
            }
            if(err.constructor.name !== errname){
              console.log(err.toString());
              throw new Error(
                `assertThrows(${cb.toString()}) failed, expected error` +
                `of type '${errname}' got type '${err.constructor.name}'`
              );
            }
            if(!pattern.test(err.message)){
              console.log(err.toString());
              throw new Error(
                `assertThrows(${cb.toString()}) failed, expected error` +
                `message to match pattern '${pattern}' got:\n${err.message}`
              );
            }
          }
        };
        assert(() => !("prototype" in pyodide.globals));
        assert(() => !("caller" in pyodide.globals));
        assert(() => !("name" in pyodide.globals));
        assert(() => "length" in pyodide.globals);
        let get_method = pyodide.globals.__getitem__;
        assert(() => "prototype" in get_method);
        assert(() => get_method.prototype === undefined);
        assert(() => !("length" in get_method));
        assert(() => !("name" in get_method));

        assert(() => pyodide.globals.get.type === "builtin_function_or_method");
        assert(() => pyodide.globals.set.type === undefined);

        let [Test, t] = pyodide.runPython(`
            class Test: pass
            [Test, Test()]
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

        [Test, t] = pyodide.runPython(`
            class Test:
                caller="fifty"
                prototype="prototype"
                name="me"
                length=7
            [Test, Test()]
        `);
        assert(() => Test.prototype === "prototype");
        assert(() => Test.name==="me");
        assert(() => Test.length === 7);

        assert(() => t.caller === "fifty");
        assert(() => t.prototype === "prototype");
        assert(() => t.name==="me");
        assert(() => t.length === 7);


        [Test, t] = pyodide.runPython(`
            class Test:
                def __len__(self):
                    return 9
            [Test, Test()]
        `);
        assert(() => !("length" in Test));
        assert(() => t.length === 9);
        t.length = 10;
        assert(() => t.length === 10);
        assert(() => t.__len__() === 9);

        let l = pyodide.runPython(`
            l = [5, 6, 7] ; l
        `);
        assert(() => l.get.type === undefined);
        assert(() => l.get(1) === 6);
        assert(() => l.length === 3);
        l.set(0, 80);
        pyodide.runPython(`
            assert l[0] == 80
        `);
        l.delete(1);
        pyodide.runPython(`
            assert len(l) == 2 and l[1] == 7
        `);
        assert(() => l.length === 2 && l.get(1) === 7);
        """
    )


def test_errors(selenium):
    selenium.run_js(
        """
        function expect_error(func){
            let error = false;
            try {
                func();
            } catch(e) {
                if(e.name === "PythonError"){
                    error = true;
                }
            }
            if(!error){
                throw new Error(`No PythonError ocurred: ${func.toString().slice(6)}`);
            }
        }
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
        expect_error(() => t.x);
        expect_error(() => t.x = 2);
        expect_error(() => delete t.x);
        expect_error(() => Object.getOwnPropertyNames(t));
        expect_error(() => t());
        expect_error(() => t.get(1));
        expect_error(() => t.set(1, 2));
        expect_error(() => t.delete(1));
        expect_error(() => t.has(1));
        expect_error(() => t.length);
        expect_error(() => t.then(()=>{}));
        expect_error(() => t.toString());
        expect_error(() => Array.from(t));
        """
    )


def test_fatal_error(selenium_standalone):
    """Inject fatal errors in all the reasonable entrypoints"""
    selenium_standalone.run_js(
        """
        let fatal_error = false;
        pyodide._module.fatal_error = (e) => {
            fatal_error = true;
            throw e;
        }
        function expect_fatal(func){
            fatal_error = false;
            try {
                func();
            } catch(e) {
                // pass
            } finally {
                if(!fatal_error){
                    throw new Error(`No fatal error occured: ${func.toString().slice(6)}`);
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
        expect_fatal(() => t.then(()=>{}));
        expect_fatal(() => t.toString());
        expect_fatal(() => Array.from(t));
        expect_fatal(() => t.destroy());
        expect_fatal(() => t.destroy());
        a = pyodide.runPython(`
            from array import array
            array("I", [1,2,3,4])
        `);
        b = a.getBuffer();
        b._view_ptr = 1e10;
        expect_fatal(() => b.release());
        """
    )
