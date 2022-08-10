import re
from collections.abc import Sequence
from textwrap import dedent
from typing import Any

import pytest
from pytest_pyodide import run_in_pyodide

from pyodide.code import CodeRunner, eval_code, find_imports, should_quiet  # noqa: E402


def _strip_assertions_stderr(messages: Sequence[str]) -> list[str]:
    """Strip additional messages on stderr included when ASSERTIONS=1"""
    res = []
    for msg in messages:
        if msg.strip() in [
            "sigaction: signal type not supported: this is a no-op.",
            "Calling stub instead of siginterrupt()",
        ]:
            continue
        res.append(msg)
    return res


def test_find_imports():

    res = find_imports(
        """
        import numpy as np
        from scipy import sparse
        import matplotlib.pyplot as plt
        """
    )
    assert set(res) == {"numpy", "scipy", "matplotlib"}

    # If there is a syntax error in the code, find_imports should return empty
    # list.
    res = find_imports(
        """
        import numpy as np
        from scipy import sparse
        import matplotlib.pyplot as plt
        for x in [1,2,3]
        """
    )
    assert res == []


def test_pyimport(selenium):
    selenium.run_js(
        """
        let platform = pyodide.pyimport("platform");
        assert(() => platform.machine() === "wasm32");
        assert(() => !pyodide.globals.has("platform"))
        assertThrows(() => pyodide.pyimport("platform;"), "PythonError", "ModuleNotFoundError: No module named 'platform;'");
        platform.destroy();
        """
    )


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

    l = cr.ast.body[0].value.left  # type: ignore[attr-defined]
    cr.ast.body[0].value.left = ast.BinOp(  # type: ignore[attr-defined]
        left=l, op=ast.Mult(), right=ast.Constant(value=2)
    )
    assert cr.compile().run({"x": 3}) == 13

    # Code transform
    cr.code = cr.code.replace(co_consts=(0, 3, 5, None))
    assert cr.run({"x": 4}) == 17


def test_code_runner_mode():
    from codeop import PyCF_DONT_IMPLY_DEDENT  # type: ignore[attr-defined]

    assert CodeRunner("1+1\n1+1", mode="exec").compile().run() == 2
    with pytest.raises(SyntaxError, match="invalid syntax"):
        CodeRunner("1+1\n1+1", mode="eval").compile().run()
    with pytest.raises(
        SyntaxError,
        match="multiple statements found while compiling a single statement",
    ):
        CodeRunner("1+1\n1+1", mode="single").compile().run()
    with pytest.raises(SyntaxError, match="invalid syntax"):
        CodeRunner(
            "def f():\n  1", mode="single", flags=PyCF_DONT_IMPLY_DEDENT
        ).compile().run()


def test_eval_code():
    ns: dict[str, Any] = {}
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
    globals: dict[str, Any] = {}
    eval_code("x=2", globals, {})
    with pytest.raises(NameError):
        eval_code("x", globals, {})

    locals: dict[str, Any] = {}
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


def test_unpack_archive(selenium_standalone):
    selenium = selenium_standalone
    js_error = selenium.run_js(
        """
        var error = "";
        try {
            pyodide.unpackArchive([1, 2, 3], "zip", "abc");
        } catch (te) {
            error = te.toString();
        }
        return error
        """
    )
    expected_err_msg = "TypeError: Expected argument 'buffer' to be an ArrayBuffer or an ArrayBuffer view"
    assert js_error == expected_err_msg


@run_in_pyodide
def test_dup_pipe(selenium):
    # See https://github.com/emscripten-core/emscripten/issues/14640
    import os

    [fdr1, fdw1] = os.pipe()
    fdr2 = os.dup(fdr1)
    fdw2 = os.dup2(fdw1, 50)
    # Closing any of fdr, fdr2, fdw, or fdw2 will currently destroy the pipe.
    # This bug is fixed upstream:
    # https://github.com/emscripten-core/emscripten/pull/14685
    s1 = b"some stuff"
    s2 = b"other stuff to write"
    os.write(fdw1, s1)
    assert os.read(fdr2, 100) == s1
    os.write(fdw2, s2)
    assert os.read(fdr1, 100) == s2


@run_in_pyodide
def test_dup_temp_file(selenium):
    # See https://github.com/emscripten-core/emscripten/issues/15012
    import os
    from tempfile import TemporaryFile

    tf = TemporaryFile(buffering=0)
    fd1 = os.dup(tf.fileno())
    os.dup2(tf.fileno(), 50)
    s = b"hello there!"
    tf.write(s)
    tf2 = open(fd1, "w+")
    assert tf2.tell() == len(s)
    # This next assertion actually demonstrates a bug in dup: the correct value
    # to return should be b"".
    assert os.read(fd1, 50) == b""
    tf2.seek(1)
    assert tf.tell() == 1
    assert tf.read(100) == b"ello there!"


@run_in_pyodide
def test_dup_stdout(selenium):
    # Test redirecting stdout using low level os.dup operations.
    # This sort of redirection is used in pytest.
    import os
    import sys
    from tempfile import TemporaryFile

    tf = TemporaryFile(buffering=0)
    save_stdout = os.dup(sys.stdout.fileno())
    os.dup2(tf.fileno(), sys.stdout.fileno())
    print("hi!!")
    print("there...")
    assert tf.tell() == len("hi!!\nthere...\n")
    os.dup2(save_stdout, sys.stdout.fileno())
    print("not captured")
    os.dup2(tf.fileno(), sys.stdout.fileno())
    print("captured")
    assert tf.tell() == len("hi!!\nthere...\ncaptured\n")
    os.dup2(save_stdout, sys.stdout.fileno())
    os.close(save_stdout)
    tf.seek(0)
    assert tf.read(1000).decode() == "hi!!\nthere...\ncaptured\n"


@pytest.mark.skip_pyproxy_check
def test_monkeypatch_eval_code(selenium):
    try:
        selenium.run(
            """
            import pyodide
            old_eval_code = pyodide.code.eval_code
            x = 3
            def eval_code(code, ns):
                return [ns["x"], old_eval_code(code, ns)]
            pyodide.code.eval_code = eval_code
            """
        )
        assert selenium.run("x = 99; 5") == [3, 5]
        assert selenium.run("7") == [99, 7]
    finally:
        selenium.run(
            """
            pyodide.code.eval_code = old_eval_code
            """
        )


def test_hiwire_is_promise(selenium):
    for s in [
        "0",
        "1",
        "'x'",
        "''",
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

    if not selenium.browser == "node":
        assert selenium.run_js(
            "return pyodide._module.hiwire.isPromise(document.all) === false;"
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
        let x = new Int8Array(1);
        pyodide.setInterruptBuffer(x);
        self.triggerKeyboardInterrupt = function(){
            x[0] = 2;
        }
        try {
            pyodide.runPython(`
                from js import triggerKeyboardInterrupt
                for x in range(100000):
                    if x == 2000:
                        triggerKeyboardInterrupt()
            `);
        } catch(e){}
        pyodide.setInterruptBuffer(undefined);
        return pyodide.globals.get('x');
        """
    )
    assert 2000 < x < 2500


def test_run_python_async_toplevel_await(selenium):
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            from js import fetch
            resp = await fetch("repodata.json")
            json = (await resp.json()).to_py()["packages"]
            assert "micropip" in json
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


def test_check_interrupt(selenium):
    assert selenium.run_js(
        """
        let buffer = new Uint8Array(1);
        let x = 0;
        pyodide.setInterruptBuffer(buffer);
        function test(){
            buffer[0] = 2;
            pyodide.checkInterrupt();
            x = 1;
        }
        self.test = test;
        let err;
        try {
            pyodide.runPython(`
                from js import test;
                test();
            `);
        } catch(e){
            err = e;
        }
        return x === 0 && err.message.includes("KeyboardInterrupt");
        """
    )

    assert selenium.run_js(
        """
        let buffer = new Uint8Array(1);
        pyodide.setInterruptBuffer(buffer);
        buffer[0] = 2;
        let err_code = 0;
        for(let i = 0; i < 1000; i++){
            err_code = err_code || pyodide._module._PyErr_CheckSignals();
        }
        let err_occurred = pyodide._module._PyErr_Occurred();
        console.log({err_code, err_occurred});
        pyodide._module._PyErr_Clear();
        return buffer[0] === 0 && err_code === -1 && err_occurred !== 0;
        """
    )


def test_check_interrupt_custom_signal_handler(selenium):
    try:
        selenium.run_js(
            """
            pyodide.runPython(`
                import signal
                interrupt_occurred = False
                def signal_handler(*args):
                    global interrupt_occurred
                    interrupt_occurred = True
                signal.signal(signal.SIGINT, signal_handler)
                None
            `);
            """
        )
        selenium.run_js(
            """
            let buffer = new Uint8Array(1);
            let x = 0;
            pyodide.setInterruptBuffer(buffer);
            function test(){
                buffer[0] = 2;
                pyodide.checkInterrupt();
                x = 1;
            }
            self.test = test;
            let err;
            pyodide.runPython(`
                interrupt_occurred = False
                from js import test
                test()
                assert interrupt_occurred == True
                del test
            `);
            """
        )
        assert selenium.run_js(
            """
            pyodide.runPython(`
                interrupt_occurred = False
            `);
            let buffer = new Uint8Array(1);
            pyodide.setInterruptBuffer(buffer);
            buffer[0] = 2;
            let err_code = 0;
            for(let i = 0; i < 1000; i++){
                err_code = err_code || pyodide._module._PyErr_CheckSignals();
            }
            let interrupt_occurred = pyodide.globals.get("interrupt_occurred");

            return buffer[0] === 0 && err_code === 0 && interrupt_occurred;
            """
        )
    finally:
        # Restore signal handler
        selenium.run_js(
            """
            pyodide.runPython(`
                import signal
                signal.signal(signal.SIGINT, signal.default_int_handler)
                None
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
        self.throwError = throwError;
        pyodide.runPython(`
            from js import throwError
            from unittest import TestCase
            from pyodide.ffi import JsException
            raises = TestCase().assertRaisesRegex
            with raises(JsException, "blah!"):
                throwError()
        `);
        """
    )


def test_create_once_callable(selenium):
    selenium.run_js(
        """
        self.call7 = function call7(f){
            return f(7);
        }
        pyodide.runPython(`
            from pyodide.ffi import create_once_callable, JsException
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
        self.testAddListener = function(f){
            self.listener = f;
        }
        self.testCallListener = function(f){
            return self.listener();
        }
        self.testRemoveListener = function(f){
            return self.listener === f;
        }
        pyodide.runPython(`
            from pyodide.ffi import create_proxy
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


def test_return_destroyed_value(selenium):
    selenium.run_js(
        r"""
        self.f = function(x){ return x };
        pyodide.runPython(`
            from pyodide.ffi import create_proxy, JsException
            from js import f
            p = create_proxy([])
            p.destroy()
            try:
                f(p)
            except JsException as e:
                assert str(e) == (
                    "Error: Object has already been destroyed\\n"
                    'The object was of type "list" and had repr "[]"'
                )
        `);
        """
    )


def test_docstrings_a():
    from _pyodide.docstring import dedent_docstring, get_cmeth_docstring
    from pyodide.ffi import JsProxy

    jsproxy = JsProxy()
    c_docstring = get_cmeth_docstring(jsproxy.then)
    assert c_docstring == "then(onfulfilled, onrejected)\n--\n\n" + dedent_docstring(
        jsproxy.then.__doc__
    )


def test_docstrings_b(selenium):
    from _pyodide.docstring import dedent_docstring
    from pyodide.ffi import JsProxy, create_once_callable

    jsproxy = JsProxy()
    ds_then_should_equal = dedent_docstring(jsproxy.then.__doc__)
    sig_then_should_equal = "(onfulfilled, onrejected)"
    ds_once_should_equal = dedent_docstring(create_once_callable.__doc__)
    sig_once_should_equal = "(obj, /)"
    selenium.run_js("self.a = Promise.resolve();")
    [ds_then, sig_then, ds_once, sig_once] = selenium.run(
        """
        from js import a
        from pyodide.ffi import create_once_callable as b
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
        let state = pyodide._api.saveState();

        pyodide.registerJsModule("c", { thirdfield : 9 });
        pyodide.runPython("y = 77; from b import otherfield; import c;");
        pyodide._api.restoreState(state);
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
        x = re.sub("/lib/python.*/", "", x)
        x = re.sub("warning: no [bB]lob.*\n", "", x)
        x = re.sub("Error: intentionally triggered fatal error!\n", "", x)
        x = re.sub(" +at .*\n", "", x)
        x = re.sub(".*@https?://[0-9.:]*/.*\n", "", x)
        x = re.sub(".*@debugger.*\n", "", x)
        x = re.sub(".*@chrome.*\n", "", x)
        x = x.replace("\n\n", "\n")
        return x

    err_msg = strip_stack_trace(selenium_standalone.logs)
    err_msg = "".join(_strip_assertions_stderr(err_msg.splitlines(keepends=True)))
    assert (
        err_msg
        == dedent(
            strip_stack_trace(
                """
                Python initialization complete
                Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.
                The cause of the fatal error was:
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
        assert(() => pyodide._api.runPython("1+1") === 2);
        """
    )


def test_reentrant_error(selenium):
    caught = selenium.run_js(
        """
        function raisePythonKeyboardInterrupt(){
            pyodide.globals.get("pyfunc")();
        }
        let caught = false;
        try {
            pyodide.runPython(`
                def pyfunc():
                    raise KeyboardInterrupt
                from js import raisePythonKeyboardInterrupt
                try:
                    raisePythonKeyboardInterrupt()
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


def test_js_stackframes(selenium):
    res = selenium.run_js(
        """
        self.b = function b(){
            pyodide.pyimport("???");
        }
        self.d1 = function d1(){
            pyodide.runPython("c2()");
        }
        self.d2 = function d2(){
            d1();
        }
        self.d3 = function d3(){
            d2();
        }
        self.d4 = function d4(){
            d3();
        }
        pyodide.runPython(`
            def c1():
                from js import b
                b()
            def c2():
                c1()
            def e():
                from js import d4
                from pyodide.ffi import to_js
                from traceback import extract_tb
                try:
                    d4()
                except Exception as ex:
                    return to_js([[x.filename, x.name] for x in extract_tb(ex.__traceback__)])
        `);
        let e = pyodide.globals.get("e");
        let res = e();
        e.destroy();
        return res;
        """
    )

    def normalize_tb(t):
        res = []
        for [file, name] in t:
            if file.endswith((".js", ".html")):
                file = file.rpartition("/")[-1]
            if file.endswith(".py"):
                file = "/".join(file.split("/")[-2:])
            if (
                re.fullmatch(r"\:[0-9]*", file)
                or file == "evalmachine.<anonymous>"
                or file == "debugger eval code"
            ):
                file = "test.html"
            res.append([file, name])
        return res

    frames = [
        ["<exec>", "e"],
        ["test.html", "d4"],
        ["test.html", "d3"],
        ["test.html", "d2"],
        ["test.html", "d1"],
        ["pyodide.asm.js", "runPython"],
        ["_pyodide/_base.py", "eval_code"],
        ["_pyodide/_base.py", "run"],
        ["<exec>", "<module>"],
        ["<exec>", "c2"],
        ["<exec>", "c1"],
        ["test.html", "b"],
        ["pyodide.asm.js", "pyimport"],
        ["importlib/__init__.py", "import_module"],
    ]
    assert normalize_tb(res[: len(frames)]) == frames


def test_reentrant_fatal(selenium_standalone):
    selenium = selenium_standalone
    assert selenium.run_js(
        """
        function f(){
            pyodide.globals.get("trigger_fatal_error")();
        }
        self.success = true;
        try {
            pyodide.runPython(`
                from _pyodide_core import trigger_fatal_error
                from js import f
                try:
                    f()
                except Exception as e:
                    # This code shouldn't be executed
                    import js
                    js.success = False
            `);
        } catch(e){}
        return success;
        """
    )


def test_weird_throws(selenium):
    """Throw strange Javascript garbage and make sure we survive."""
    selenium.run_js(
        '''
        self.funcs = {
            null(){ throw null; },
            undefined(){ throw undefined; },
            obj(){ throw {}; },
            obj_null_proto(){ throw Object.create(null); },
            string(){ throw "abc"; },
            func(){ throw self.funcs.func; },
            number(){ throw 12; },
            bigint(){ throw 12n; },
        };
        pyodide.runPython(`
            from js import funcs
            from unittest import TestCase
            from pyodide.ffi import JsException
            raises = TestCase().assertRaisesRegex
            msgs = {
                "null" : ['type object .* tag .object Null.', '"""null"""',  'fails'],
                "undefined" : ['type undefined .* tag .object Undefined.', '"""undefined"""',  'fails'],
                "obj" : ['type object .* tag .object Object.', '""".object Object."""',  '""".object Object."""'],
                "obj_null_proto" : ['type object .* tag .object Object.', 'fails',  'fails'],
                "string" : ["Error: abc"],
                "func" : ['type function .* tag .object Function.', 'throw self.funcs.func',  'throw self.funcs.func'],
                "number" : ['type number .* tag .object Number.'],
                "bigint" : ['type bigint .* tag .object BigInt.'],
            }
            for name, f in funcs.object_entries():
                msg = '.*\\\\n.*'.join(msgs.get(name, ["xx"]))
                with raises(JsException, msg):
                    f()
        `);
        '''
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@pytest.mark.parametrize("to_throw", ["Object.create(null);", "'Some message'", "null"])
def test_weird_fatals(selenium_standalone, to_throw):
    expected_message = {
        "Object.create(null);": "Error: A value of type object with tag [object Object] was thrown as an error!",
        "'Some message'": "Error: Some message",
        "null": "Error: A value of type object with tag [object Null] was thrown as an error!",
    }[to_throw]
    msg = selenium_standalone.run_js(
        f"""
        self.f = function(){{ throw {to_throw} }};
        """
        """
        try {
            pyodide.runPython(`
                from _pyodide_core import raw_call
                from js import f
                raw_call(f)
            `);
        } catch(e){
            return e.toString();
        }
        """
    )
    print("msg", msg[: len(expected_message)])
    print("expected_message", expected_message)
    assert msg[: len(expected_message)] == expected_message


def test_restore_error(selenium):
    # See PR #1816.
    selenium.run_js(
        """
        self.f = function(){
            pyodide.runPython(`
                err = Exception('hi')
                raise err
            `);
        }
        pyodide.runPython(`
            from js import f
            import sys
            try:
                f()
            except Exception as e:
                assert err == e
                assert e == sys.last_value
            finally:
                del err
            assert sys.getrefcount(sys.last_value) == 2
        `);
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_custom_stdin_stdout(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    strings = [
        "hello world",
        "hello world\n",
        "This has a \x00 null byte in the middle...",
        "several\nlines\noftext",
        "pyodidé",
        "碘化物",
        "🐍",
    ]
    selenium.run_js(
        """
        function* stdinStrings(){
            for(let x of %s){
                yield x;
            }
        }
        let stdinStringsGen = stdinStrings();
        function stdin(){
            return stdinStringsGen.next().value;
        }
        self.stdin = stdin;
        """
        % strings
    )
    selenium.run_js(
        """
        self.stdoutStrings = [];
        self.stderrStrings = [];
        function stdout(s){
            stdoutStrings.push(s);
        }
        function stderr(s){
            stderrStrings.push(s);
        }
        let pyodide = await loadPyodide({
            fullStdLib: false,
            jsglobals : self,
            stdin,
            stdout,
            stderr,
        });
        self.pyodide = pyodide;
        globalThis.pyodide = pyodide;
        """
    )
    outstrings: list[str] = sum((s.removesuffix("\n").split("\n") for s in strings), [])
    print(outstrings)
    assert (
        selenium.run_js(
            f"""
        return pyodide.runPython(`
            [input() for x in range({len(outstrings)})]
            # ... test more stuff
        `).toJs();
        """
        )
        == outstrings
    )

    [stdoutstrings, stderrstrings] = selenium.run_js(
        """
        pyodide.runPython(`
            import sys
            print("something to stdout")
            print("something to stderr",file=sys.stderr)
        `);
        return [self.stdoutStrings, self.stderrStrings];
        """
    )
    assert stdoutstrings[-2:] == [
        "Python initialization complete",
        "something to stdout",
    ]
    stderrstrings = _strip_assertions_stderr(stderrstrings)
    assert stderrstrings == ["something to stderr"]


def test_home_directory(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    home = "/home/custom_home"
    selenium.run_js(
        """
        let pyodide = await loadPyodide({
            homedir : "%s",
        });
        return pyodide.runPython(`
            import os
            os.getcwd() == "%s"
        `)
        """
        % (home, home)
    )


def test_sys_path0(selenium):
    selenium.run_js(
        """
        pyodide.runPython(`
            import sys
            import os
            assert os.getcwd() == sys.path[0]
        `)
        """
    )


@run_in_pyodide
def test_run_js(selenium):
    from unittest import TestCase

    from pyodide.code import run_js

    raises = TestCase().assertRaises

    with raises(TypeError, msg="argument should have type 'string' not type 'int'"):
        run_js(3)  # type: ignore[arg-type]

    assert run_js("(x)=> x+1")(7) == 8
    assert run_js("[1,2,3]")[2] == 3
    run_js("globalThis.x = 77")
    from js import x

    assert x == 77


@run_in_pyodide
def test_pickle_jsexception(selenium):
    import pickle

    from pyodide.code import run_js

    pickle.dumps(run_js("new Error('hi');"))


def test_raises_jsexception(selenium):
    from pyodide.ffi import JsException

    @run_in_pyodide
    def raise_jsexception(selenium):
        from pyodide.code import run_js

        run_js("throw new Error('hi');")

    with pytest.raises(JsException, match="Error: hi"):
        raise_jsexception(selenium)


@run_in_pyodide(packages=["pytest"])
def test_moved_deprecation_warnings(selenium_standalone):
    import pytest

    import pyodide
    from pyodide import DEPRECATED_LIST, code, ffi, http  # noqa: F401

    for func, mod in DEPRECATED_LIST.items():
        getattr(getattr(pyodide, mod), func)

    for func, mod in DEPRECATED_LIST.items():
        with pytest.warns(FutureWarning, match=mod):
            getattr(pyodide, func)

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for func in DEPRECATED_LIST.keys():
            getattr(pyodide, func)
