# See also test_typeconversions, and test_python.
import pytest


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
    assert selenium.run("from js import ImageData\n" "ImageData.new(64, 64)")
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
          var nextIndex = 0;
          return {
            next: function() {
              return nextIndex < array.length ?
                {value: array[nextIndex++], done: False} :
                {done: True};
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
        );
        """
        )
        == list(range(10))
    )


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


@pytest.mark.xfail
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
            a.f(y=10, x=2) == [a, x, y]
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
            f"return pyodide._module.hiwire.function_supports_kwargs({repr(s)})"
        ) == res
