import pytest
from pathlib import Path
import sys
from textwrap import dedent

sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "py"))

from pyodide import find_imports, eval_code  # noqa: E402
from pyodide._base import CodeRunner, should_quiet  # noqa: E402


def test_find_imports():

    res = find_imports(
        dedent(
            """
           import numpy as np
           from scipy import sparse
           import matplotlib.pyplot as plt
           """
        )
    )
    assert set(res) == {"numpy", "scipy", "matplotlib"}


def test_code_runner():
    assert should_quiet("1+1;")
    assert not should_quiet("1+1#;")
    assert not should_quiet("5-2  # comment with trailing semicolon ;")

    # Normal usage
    assert CodeRunner("1+1").compile().run() == 2
    assert CodeRunner("1+1\n1+1").compile().run() == 2
    assert CodeRunner("x + 7").compile().run({"x": 3}) == 10
    cr = CodeRunner("x + 7")

    # Ast transform
    import ast

    l = cr.ast.body[0].value.left
    cr.ast.body[0].value.left = ast.BinOp(
        left=l, op=ast.Mult(), right=ast.Constant(value=2)
    )
    assert cr.compile().run({"x": 3}) == 13

    # Code transform
    cr.code = cr.code.replace(co_consts=(0, 3, 5, None))
    assert cr.run({"x": 4}) == 17


def test_code_runner_mode():
    from codeop import PyCF_DONT_IMPLY_DEDENT

    assert CodeRunner("1+1\n1+1", mode="exec").compile().run() == 2
    with pytest.raises(SyntaxError, match="invalid syntax"):
        CodeRunner("1+1\n1+1", mode="eval").compile().run()
    with pytest.raises(
        SyntaxError,
        match="multiple statements found while compiling a single statement",
    ):
        CodeRunner("1+1\n1+1", mode="single").compile().run()
    with pytest.raises(SyntaxError, match="unexpected EOF while parsing"):
        CodeRunner(
            "def f():\n  1", mode="single", flags=PyCF_DONT_IMPLY_DEDENT
        ).compile().run()


def test_eval_code():
    ns = {}
    assert (
        eval_code(
            """
        def f(x):
            return 2*x + 5
        f(77)
    """,
            ns,
        )
        == 2 * 77 + 5
    )
    assert ns["f"](7) == 2 * 7 + 5

    assert eval_code("(x:=4)", ns) == 4
    assert ns["x"] == 4
    assert eval_code("x=7", ns) is None
    assert ns["x"] == 7

    # default return_mode ('last_expr'), semicolon
    assert eval_code("1+1;", ns) is None
    assert eval_code("1+1#;", ns) == 2
    assert eval_code("5-2  # comment with trailing semicolon ;", ns) == 3
    assert eval_code("4//2\n", ns) == 2
    assert eval_code("2**1\n\n", ns) == 2
    assert eval_code("4//2;\n", ns) is None
    assert eval_code("2**1;\n\n", ns) is None

    # 'last_expr_or_assign' return_mode, semicolon
    assert eval_code("1 + 1", ns, return_mode="last_expr_or_assign") == 2
    assert eval_code("x = 1 + 1", ns, return_mode="last_expr_or_assign") == 2
    assert eval_code("a = 5 ; a += 1", ns, return_mode="last_expr_or_assign") == 6
    assert eval_code("a = 5 ; a += 1;", ns, return_mode="last_expr_or_assign") is None
    assert (
        eval_code("l = [1, 1, 2] ; l[0] = 0", ns, return_mode="last_expr_or_assign")
        is None
    )
    assert eval_code("a = b = 2", ns, return_mode="last_expr_or_assign") == 2

    # 'none' return_mode, (useless) semicolon
    assert eval_code("1 + 1", ns, return_mode="none") is None
    assert eval_code("x = 1 + 1", ns, return_mode="none") is None
    assert eval_code("a = 5 ; a += 1", ns, return_mode="none") is None
    assert eval_code("a = 5 ; a += 1;", ns, return_mode="none") is None
    assert eval_code("l = [1, 1, 2] ; l[0] = 0", ns, return_mode="none") is None

    # with 'quiet_trailing_semicolon' set to False
    assert eval_code("1+1;", ns, quiet_trailing_semicolon=False) == 2
    assert eval_code("1+1#;", ns, quiet_trailing_semicolon=False) == 2
    assert (
        eval_code(
            "5-2  # comment with trailing semicolon ;",
            ns,
            quiet_trailing_semicolon=False,
        )
        == 3
    )
    assert eval_code("4//2\n", ns, quiet_trailing_semicolon=False) == 2
    assert eval_code("2**1\n\n", ns, quiet_trailing_semicolon=False) == 2
    assert eval_code("4//2;\n", ns, quiet_trailing_semicolon=False) == 2
    assert eval_code("2**1;\n\n", ns, quiet_trailing_semicolon=False) == 2


def test_eval_code_locals():
    globals = {}
    eval_code("x=2", globals, {})
    with pytest.raises(NameError):
        eval_code("x", globals, {})

    locals = {}
    eval_code("import sys; sys.getrecursionlimit()", globals, locals)
    with pytest.raises(NameError):
        eval_code("sys.getrecursionlimit()", globals, {})
    eval_code("sys.getrecursionlimit()", globals, locals)

    eval_code(
        "from importlib import invalidate_caches; invalidate_caches()", globals, locals
    )
    with pytest.raises(NameError):
        eval_code("invalidate_caches()", globals, globals)
    eval_code("invalidate_caches()", globals, locals)


def test_monkeypatch_eval_code(selenium):
    try:
        selenium.run(
            """
            import pyodide
            old_eval_code = pyodide.eval_code
            x = 3
            def eval_code(code, ns):
                return [ns["x"], old_eval_code(code, ns)]
            pyodide.eval_code = eval_code
            """
        )
        assert selenium.run("x = 99; 5") == [3, 5]
        assert selenium.run("7") == [99, 7]
    finally:
        selenium.run(
            """
            pyodide.eval_code = old_eval_code
            """
        )


def test_hiwire_is_promise(selenium):
    for s in [
        "0",
        "1",
        "'x'",
        "''",
        "document.all",
        "false",
        "undefined",
        "null",
        "NaN",
        "0n",
        "[0,1,2]",
        "[]",
        "{}",
        "{a : 2}",
        "(()=>{})",
        "((x) => x*x)",
        "(function(x, y){ return x*x + y*y; })",
        "Array",
        "Map",
        "Set",
        "Promise",
        "new Array()",
        "new Map()",
        "new Set()",
    ]:
        assert selenium.run_js(
            f"return pyodide._module.hiwire.isPromise({s}) === false;"
        )

    assert selenium.run_js(
        "return pyodide._module.hiwire.isPromise(Promise.resolve()) === true;"
    )

    assert selenium.run_js(
        """
        return pyodide._module.hiwire.isPromise(new Promise((resolve, reject) => {}));
        """
    )

    assert not selenium.run_js(
        """
        let d = pyodide.runPython("{}");
        try {
            return pyodide._module.hiwire.isPromise(d);
        } finally {
            d.destroy();
        }
        """
    )


def test_keyboard_interrupt(selenium):
    x = selenium.run_js(
        """
        x = new Int8Array(1)
        pyodide._module.setInterruptBuffer(x)
        window.triggerKeyboardInterrupt = function(){
            x[0] = 2;
        }
        try {
            pyodide.runPython(`
                from js import triggerKeyboardInterrupt
                x = 0
                while True:
                    x += 1
                    if x == 2000:
                        triggerKeyboardInterrupt()
            `)
        } catch(e){}
        return pyodide.runPython('x')
        """
    )
    assert 2000 < x < 2500


def test_run_python_async_toplevel_await(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            from js import fetch
            resp = await fetch("packages.json")
            json = await resp.json()
            assert hasattr(json, "dependencies")
        `);
        """
    )


def test_run_python_proxy_leak(selenium):
    selenium.run_js(
        """
        pyodide.runPython("")
        await pyodide.runPythonAsync("")
        """
    )


def test_run_python_last_exc(selenium):
    selenium.run_js(
        """
        try {
            pyodide.runPython("x = ValueError(77); raise x");
        } catch(e){}
        pyodide.runPython(`
            import sys
            assert sys.last_value is x
            assert sys.last_type is type(x)
            assert sys.last_traceback is x.__traceback__
        `);
        """
    )


def test_async_leak(selenium):
    assert 0 == selenium.run_js(
        """
        pyodide.runPython(`d = 888.888`);
        pyodide.runPython(`async def test(): return d`);
        async function test(){
            let t = pyodide.runPython(`test()`);
            await t;
            t.destroy();
        }
        await test();
        let init_refcount = pyodide.runPython(`from sys import getrefcount; getrefcount(d)`);
        await test(); await test(); await test(); await test();
        let new_refcount = pyodide.runPython(`getrefcount(d)`);
        return new_refcount - init_refcount;
        """
    )


def test_run_python_js_error(selenium):
    selenium.run_js(
        """
        function throwError(){
            throw new Error("blah!");
        }
        window.throwError = throwError;
        pyodide.runPython(`
            from js import throwError
            from unittest import TestCase
            from pyodide import JsException
            raises = TestCase().assertRaisesRegex
            with raises(JsException, "blah!"):
                throwError()
        `);
        """
    )


def test_create_once_callable(selenium):
    selenium.run_js(
        """
        window.call7 = function call7(f){
            return f(7);
        }
        pyodide.runPython(`
            from pyodide import create_once_callable, JsException
            from js import call7;
            from unittest import TestCase
            raises = TestCase().assertRaisesRegex
            class Square:
                def __call__(self, x):
                    return x*x

                def __del__(self):
                    global destroyed
                    destroyed = True

            f = Square()
            import sys
            assert sys.getrefcount(f) == 2
            proxy = create_once_callable(f)
            assert sys.getrefcount(f) == 3
            assert call7(proxy) == 49
            assert sys.getrefcount(f) == 2
            with raises(JsException, "can only be called once"):
                call7(proxy)
            destroyed = False
            del f
            assert destroyed == True
            del proxy
        `);
        """
    )


def test_create_proxy(selenium):
    selenium.run_js(
        """
        window.testAddListener = function(f){
            window.listener = f;
        }
        window.testCallListener = function(f){
            return window.listener();
        }
        window.testRemoveListener = function(f){
            return window.listener === f;
        }
        pyodide.runPython(`
            from pyodide import create_proxy
            from js import testAddListener, testCallListener, testRemoveListener;
            class Test:
                def __call__(self):
                    return 7

                def __del__(self):
                    global destroyed
                    destroyed = True

            f = Test()
            import sys
            assert sys.getrefcount(f) == 2
            proxy = create_proxy(f)
            assert sys.getrefcount(f) == 3
            assert proxy() == 7
            testAddListener(proxy)
            assert sys.getrefcount(f) == 3
            assert testCallListener() == 7
            assert sys.getrefcount(f) == 3
            assert testCallListener() == 7
            assert sys.getrefcount(f) == 3
            assert testRemoveListener(proxy)
            assert sys.getrefcount(f) == 3
            proxy.destroy()
            assert sys.getrefcount(f) == 2
            destroyed = False
            del f
            assert destroyed == True
        `);
        """
    )


def test_docstrings_a():
    from _pyodide.docstring import get_cmeth_docstring, dedent_docstring
    from pyodide import JsProxy

    jsproxy = JsProxy()
    c_docstring = get_cmeth_docstring(jsproxy.then)
    assert c_docstring == "then(onfulfilled, onrejected)\n--\n\n" + dedent_docstring(
        jsproxy.then.__doc__
    )


def test_docstrings_b(selenium):
    from pyodide import create_once_callable, JsProxy
    from _pyodide.docstring import dedent_docstring

    jsproxy = JsProxy()
    ds_then_should_equal = dedent_docstring(jsproxy.then.__doc__)
    sig_then_should_equal = "(onfulfilled, onrejected)"
    ds_once_should_equal = dedent_docstring(create_once_callable.__doc__)
    sig_once_should_equal = "(obj)"
    selenium.run_js("window.a = Promise.resolve();")
    [ds_then, sig_then, ds_once, sig_once] = selenium.run(
        """
        from js import a
        from pyodide import create_once_callable as b
        [
            a.then.__doc__, a.then.__text_signature__,
            b.__doc__, b.__text_signature__
        ]
        """
    )
    assert ds_then == ds_then_should_equal
    assert sig_then == sig_then_should_equal
    assert ds_once == ds_once_should_equal
    assert sig_once == sig_once_should_equal


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_restore_state(selenium):
    selenium.run_js(
        """
        pyodide.registerJsModule("a", {somefield : 82});
        pyodide.registerJsModule("b", { otherfield : 3 });
        pyodide.runPython("x = 7; from a import somefield");
        let state = pyodide._module.saveState();

        pyodide.registerJsModule("c", { thirdfield : 9 });
        pyodide.runPython("y = 77; from b import otherfield; import c;");
        pyodide._module.restoreState(state);
        state.destroy();
        """
    )

    selenium.run(
        """
        from unittest import TestCase
        raises = TestCase().assertRaises
        import sys

        assert x == 7
        assert "a" in sys.modules
        assert somefield == 82
        with raises(NameError):
            y
        with raises(NameError):
            otherfield
        assert "b" not in sys.modules
        import b
        with raises(ModuleNotFoundError):
            import c
        """
    )


@pytest.mark.skip_refcount_check
def test_fatal_error(selenium_standalone):
    assert selenium_standalone.run_js(
        """
        try {
            pyodide.runPython(`
                from _pyodide_core import trigger_fatal_error
                def f():
                    g()
                def g():
                    h()
                def h():
                    trigger_fatal_error()
                f()
            `);
        } catch(e){
            return e.toString();
        }
        """
    )
    import re

    def strip_stack_trace(x):
        x = re.sub("\n.*site-packages.*", "", x)
        x = re.sub("/lib/python.*/", "", x)
        return x

    assert (
        strip_stack_trace(selenium_standalone.logs)
        == dedent(
            strip_stack_trace(
                """
            Python initialization complete
            Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.
            The cause of the fatal error was:
            {}
            Stack (most recent call first):
              File "<exec>", line 8 in h
              File "<exec>", line 6 in g
              File "<exec>", line 4 in f
              File "<exec>", line 9 in <module>
              File "/lib/pythonxxx/site-packages/pyodide/_base.py", line 242 in run
              File "/lib/pythonxxx/site-packages/pyodide/_base.py", line 344 in eval_code
            """
            )
        ).strip()
    )
    selenium_standalone.run_js(
        """
        assertThrows(() => pyodide.runPython, "Error", "Pyodide already fatally failed and can no longer be used.")
        assertThrows(() => pyodide.globals, "Error", "Pyodide already fatally failed and can no longer be used.")
        assert(() => pyodide._module.runPython("1+1") === 2);
        """
    )


def test_reentrant_error(selenium):
    caught = selenium.run_js(
        """
        function a(){
            pyodide.globals.get("pyfunc")();
        }
        let caught = false;
        try {
            pyodide.runPython(`
                def pyfunc():
                    raise KeyboardInterrupt
                from js import a
                try:
                    a()
                except Exception as e:
                    pass
            `);
        } catch(e){
            caught = true;
        }
        return caught;
        """
    )
    assert caught
