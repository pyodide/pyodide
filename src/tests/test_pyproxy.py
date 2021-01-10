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
    assert selenium.run_js("return pyodide.pyimport('f').get_value(2)") == 128
    assert selenium.run_js("return pyodide.pyimport('f').bar") == 42
    assert selenium.run_js("return ('bar' in pyodide.pyimport('f'))")
    selenium.run_js("f = pyodide.pyimport('f'); f.baz = 32")
    assert selenium.run("f.baz") == 32
    assert set(
        selenium.run_js("return Object.getOwnPropertyNames(pyodide.pyimport('f'))")
    ) == set(
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
            "toString",
            "prototype",
            "arguments",
            "caller",
        ]
    )
    assert selenium.run("hasattr(f, 'baz')")
    selenium.run_js("delete pyodide.pyimport('f').baz")
    assert not selenium.run("hasattr(f, 'baz')")
    assert selenium.run_js("return pyodide.pyimport('f').toString()").startswith("<Foo")


def test_pyproxy_refcount(selenium):
    selenium.run_js("window.jsfunc = function (f) { f(); }")
    selenium.run(
        """
        import sys
        from js import window

        def pyfunc(*args, **kwargs):
            print(*args, **kwargs)
        """
    )

    # the refcount should be 2 because:
    #
    # 1. pyfunc exists
    # 2. pyfunc is referenced from the sys.getrefcount()-test below
    #
    assert selenium.run("sys.getrefcount(pyfunc)") == 2

    selenium.run(
        """
        window.jsfunc(pyfunc) # creates new PyProxy
        """
    )

    # the refcount should be 3 because:
    #
    # 1. pyfunc exists
    # 2. one reference from PyProxy to pyfunc is alive
    # 3. pyfunc is referenced from the sys.getrefcount()-test below
    #
    assert selenium.run("sys.getrefcount(pyfunc)") == 3

    selenium.run(
        """
        window.jsfunc(pyfunc) # re-used existing PyProxy
        window.jsfunc(pyfunc) # re-used existing PyProxy
        """
    )

    # the refcount should still be 3 because:
    #
    # 1. pyfunc exists
    # 2. one reference from PyProxy to pyfunc is still alive
    # 3. pyfunc is referenced from the sys.getrefcount()-test below
    #
    assert selenium.run("sys.getrefcount(pyfunc)") == 3


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
