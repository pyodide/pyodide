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
    selenium.run_js("window.f = pyodide.pyimport('f')")
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
    selenium.run_js("delete pyodide.pyimport('f').baz")
    assert not selenium.run("hasattr(f, 'baz')")
    assert selenium.run_js("return pyodide.pyimport('f').toString()").startswith("<Foo")


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
            let f = pyodide.pyimport('f');
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
