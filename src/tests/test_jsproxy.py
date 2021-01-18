# See also test_typeconversions, and test_python.
import pytest
from pyodide_build.testing import run_in_pyodide


def test_jsproxy_dir(selenium):
    result = selenium.run_js(
        """
        window.a = { x : 2, y : "9" };
        window.b = function(){};
        return pyodide.runPython(`
            from js import a
            from js import b
            [dir(a), dir(b)]
        `).deepCopyToJavascript();
        """
    )
    jsproxy_items = set(
        [
            "__bool__",
            "__class__",
            "__defineGetter__",
            "__defineSetter__",
            "__delattr__",
            "__delitem__",
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


def test_jsproxy_getattr(selenium):
    assert (
        selenium.run_js(
            """
        window.a = { x : 2, y : "9", typeof : 7 };
        return pyodide.runPython(`
            from js import a
            [ a.x, a.y, a.typeof ]
        `).deepCopyToJavascript();
        """
        )
        == [2, "9", "object"]
    )


def test_jsproxy(selenium):
    assert (
        selenium.run(
            """
        from js import document
        el = document.createElement('div')
        document.body.appendChild(el)
        document.body.children.length"""
        )
        == 1
    )
    assert selenium.run("document.body.children[0].tagName") == "DIV"
    assert selenium.run("repr(document)") == "[object HTMLDocument]"
    selenium.run_js("window.square = function (x) { return x*x; }")
    assert selenium.run("from js import square\n" "square(2)") == 4
    assert (
        selenium.run("from js import ImageData\n" "ImageData.new(64, 64).width") == 64
    )
    assert selenium.run("from js import ImageData\n" "ImageData.typeof") == "function"
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST.y
        hasattr(TEST, 'y')"""
        )
        is False
    )
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST['y']
        'y' in TEST"""
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
        window.TEST = {foo: 'bar', baz: 'bap'}
        """
    )
    assert (
        selenium.run(
            """
        from js import TEST
        dict(TEST) == {'foo': 'bar', 'baz': 'bap'}
        """
        )
        is True
    )
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
        window.ITER = makeIterator([1, 2, 3]);"""
    )
    assert selenium.run("from js import ITER\n" "list(ITER)") == [1, 2, 3]


def test_jsproxy_implicit_iter(selenium):
    selenium.run_js(
        """
        window.ITER = [1, 2, 3];"""
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
        window.f = function(){ return arguments.length; };
        return pyodide.runPython(
            `
            from js import f
            [f(*range(n)) for n in range(10)]
            `
        ).deepCopyToJavascript();
        """
        )
        == list(range(10))
    )


@pytest.mark.xfail
def test_jsproxy_call_kwargs(selenium):
    assert (
        selenium.run_js(
            """
        window.kwarg_function = ({ a = 1, b = 1 }) => {
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
        window.a = {};
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
        window.a = {};
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
        window.a = {};
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


def test_supports_kwargs(selenium):
    tests = [
        ["", False],
        ["x", False],
        ["x     ", False],
        ["{x}", True],
        ["x, y, z", False],
        ["x, y, {z}", True],
        ["x, {y}, z", False],
        ["x, {y}, {z}", True],
        ["{}", True],
        ["{} = {}", True],
        ["[] = {}", False],
        ["{} = []", True],
        ["[] = []", False],
        ["{} = null", True],
        ["x = '2, `, {y}'", False],
        ["{x} = '2, \\', x'", True],
        ["[{x}]", False],
        ["[x, y, z]", False],
        ["x,", False],
        ["{x},", True],
        ["x, { y = 2 }", True],
        ["{ y = 2 }, x", False],
        ["{ x = 2 }, { y = 2 }", True],
        ["{ a = 7, b = 2}", True],
        ["{ a = 7, b = 2} = {b : 3}", True],
        ["{ a = [7, 1], b = { c : 2} } = {}", True],
        ["{ a = 7, b = 2} = {}", True],
        ["{ a = 7, b = 2} = null", True],
        ["{ x = { y : 2 }}", True],
        ["{ x : 2 }", True],
    ]
    for (s, res) in tests:
        s = f"function f({s}){{}}"
        selenium.run_js(
            f"return pyodide._module.function_supports_kwargs({repr(s)})"
        ) == res


@run_in_pyodide
def test_import_invocation():
    import js

    def temp():
        print("okay?")

    js.setTimeout(temp, 100)
    js.fetch("packages.json")


@run_in_pyodide
def test_import_bind():
    from js import fetch

    fetch("packages.json")


@run_in_pyodide
def test_nested_attribute_access():
    import js
    from js import window

    js.URL.createObjectURL
    window.URL.createObjectURL


@run_in_pyodide
def test_window_isnt_super_weird_anymore():
    import js
    from js import window, Array

    assert window.Array != window
    assert window.Array == Array
    assert window.window.window.window == window
    assert js.window.Array == Array
    assert js.window.window.window.window == window
    assert window.window.window.window.Array == Array


def test_mount_object(selenium):
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
        return pyodide.runPython(`
            from a import x
            from b import x as x2
            result = [x(), x2()]
            import a
            import b
            result += [a.s, dir(a), dir(b)]
            result
        `).deepCopyToJavascript()
        """
    )
    assert result[:3] == ["x1", "x2", 3]
    assert set([x for x in result[3] if len(x) == 1]) == set(["x", "y", "s", "t"])
    assert set([x for x in result[4] if len(x) == 1]) == set(["x", "y", "u", "t"])


@pytest.mark.xfail
def test_mount_map(selenium):
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
        let a = new Map(Object.entries({ x : x1, y, s : 3, t : 7}));
        let b = new Map(Object.entries({ x : x2, y, u : 3, t : 7}));
        pyodide.registerJsModule("a", a);
        pyodide.registerJsModule("b", b);
        return pyodide.runPython(`
            from a import x
            from b import x as x2
            result = [x(), x2()]
            import a
            import b
            result += [a.s, dir(a), dir(b)]
            import sys
            del sys.modules["a"]
            del sys.modules["b"]
            result
        `)
        """
    )
    assert result[:3] == ["x1", "x2", 3]
    # fmt: off
    assert set(result[3]).issuperset(
        [
            "x", "y", "s", "t",
            "__dir__", "__doc__", "__getattr__", "__loader__",
            "__name__", "__package__", "__spec__",
            "jsproxy",
        ]
    )
    # fmt: on
    assert set(result[4]).issuperset(["x", "y", "u", "t", "jsproxy"])


def test_unregister_jsmodule(selenium):
    selenium.run_js(
        """
        let a = new Map(Object.entries({ s : 7 }));
        let b = new Map(Object.entries({ t : 3 }));
        pyodide.registerJsModule("a", a);
        pyodide.registerJsModule("a", b);
        pyodide.unregisterJsModule("a")
        pyodide.runPython(`
            try:
                import a
                assert False
            except ImportError:
                pass
        `)
        """
    )


def test_unregister_jsmodule_error(selenium):
    selenium.run_js(
        """
        try {
            pyodide.unregisterJsModule("doesnotexist");
            throw new Error("unregisterJsModule should have thrown an error.");
        } catch(e){
            if(!e.message.includes("Cannot unregister 'doesnotexist': no javascript module with that name is registered")){
                throw e;
            }
        }
        """
    )


def test_nested_import(selenium):
    assert (
        selenium.run_js(
            """
            window.a = { b : { c : { d : 2 } } };
            return pyodide.runPython("from js.a.b import c; c.d");
            """
        )
        == 2
    )


def test_register_jsmodule_docs_example(selenium):
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
        """
    )
