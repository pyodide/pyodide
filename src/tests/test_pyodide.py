import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Any

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import DIST_PATH, PYODIDE_ROOT, strip_assertions_stderr
from pyodide.code import CodeRunner, eval_code, find_imports, should_quiet  # noqa: E402


def test_find_imports():
    res = find_imports(
        """
        import numpy as np
        from scipy import sparse
        import matplotlib.pyplot as plt
        """
    )
    assert set(res) == {"numpy", "scipy", "matplotlib", "matplotlib.pyplot"}

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


def test_ffi_import_star():
    exec("from pyodide.ffi import *", {})


def test_pyimport1():
    from _pyodide._base import pyimport_impl

    assert pyimport_impl("pyodide").__name__ == "pyodide"
    assert pyimport_impl("pyodide.console").__name__ == "pyodide.console"
    assert pyimport_impl("pyodide.console.BANNER").startswith("Python ")


def test_pyimport2(selenium):
    selenium.run_js(
        """
        let platform = pyodide.pyimport("platform");
        assert(() => platform.machine() === "wasm32");
        assert(() => !pyodide.globals.has("platform"))
        assertThrows(() => pyodide.pyimport("platform;"), "PythonError", "ModuleNotFoundError: No module named 'platform;'");
        platform.destroy();
        """
    )


def test_pyimport3():
    from _pyodide._base import eval_code, pyimport_impl

    with TemporaryDirectory() as tempdir:
        Path(tempdir, "aaa").mkdir()
        Path(tempdir, "aaa", "bbb.py").write_text("ccc = 1")
        sys.path.insert(0, tempdir)

        aaa = pyimport_impl("aaa")
        pyimport_impl("aaa.bbb")
        del aaa.bbb.ccc

        # case 1 unload parent module
        del sys.modules["aaa"]
        assert pyimport_impl("aaa.bbb") == eval_code("from aaa import bbb; bbb")

        # case 2 delete child module
        del aaa.bbb
        assert pyimport_impl("aaa.bbb") == eval_code("from aaa import bbb; bbb")

        # case 3 recover deleted value
        with pytest.raises(ModuleNotFoundError):
            pyimport_impl("aaa.bbb.ccc")
        del sys.modules["aaa.bbb"]
        assert pyimport_impl("aaa.bbb.ccc") == 1

        sys.path.remove(tempdir)


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

    # Change to 2*x + 7
    l = cr.ast.body[0].value.left  # type: ignore[attr-defined]
    cr.ast.body[0].value.left = ast.BinOp(  # type: ignore[attr-defined]
        left=l, op=ast.Mult(), right=ast.Constant(value=2)
    )
    assert cr.compile().run({"x": 3}) == 13

    # FIXME: It looks like we originally wanted to modify the code object to 3*x + 5, but the bytecode
    #        syntax seems to have changed in Python 3.14, so this test was broken and commented out.
    # Code transform
    # assert cr.code
    # cr.code = cr.code.replace(co_consts=(0, 3, 5, None))

    assert cr.run({"x": 4}) == 15


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

    # See https://github.com/pyodide/pyodide/issues/3578
    with pytest.raises(NameError):
        eval_code("print(self)")

    res = eval_code(
        """
        var = "Hello"
        def test():
            return var
        test()
        """
    )
    assert res == "Hello"


def test_relaxed_call():
    from pyodide.code import relaxed_call

    assert relaxed_call(int, "7") == 7

    def f1(a, b):
        return [a, b]

    assert relaxed_call(f1, 1, 2) == [1, 2]
    assert relaxed_call(f1, 1, 2, 3) == [1, 2]
    assert relaxed_call(f1, 1, b=7) == [1, 7]
    assert relaxed_call(f1, a=2, b=7) == [2, 7]
    assert relaxed_call(f1, 1, b=7, c=9) == [1, 7]
    assert relaxed_call(f1, 1, 2, 3, c=9) == [1, 2]
    with pytest.raises(TypeError, match="missing a required argument: 'b'"):
        relaxed_call(f1, 1)
    with pytest.raises(TypeError, match="multiple values for argument 'b'"):
        relaxed_call(f1, 1, 2, b=3)

    def f2(a, b=7):
        return [a, b]

    assert relaxed_call(f2, 1, 2) == [1, 2]
    assert relaxed_call(f2, 1, 2, 3) == [1, 2]
    assert relaxed_call(f2, 1, b=7) == [1, 7]
    assert relaxed_call(f2, a=2, b=7) == [2, 7]
    assert relaxed_call(f2, 1, b=7, c=9) == [1, 7]
    assert relaxed_call(f2, 1, 2, 3, c=9) == [1, 2]
    assert relaxed_call(f2, 1) == [1, 7]
    with pytest.raises(TypeError, match="missing a required argument: 'a'"):
        relaxed_call(f2)

    def f3(a, *args, b=7):
        return [a, args, b]

    assert relaxed_call(f3, 1, 2) == [1, (2,), 7]
    assert relaxed_call(f3, 1, 2, 3) == [1, (2, 3), 7]
    assert relaxed_call(f3, 1, b=7) == [1, (), 7]
    assert relaxed_call(f3, a=2, b=7) == [2, (), 7]
    assert relaxed_call(f3, 1, b=7, c=9) == [1, (), 7]
    assert relaxed_call(f3, 1, 2, 3, c=9) == [1, (2, 3), 7]
    assert relaxed_call(f3, 1) == [1, (), 7]

    def f4(a, /, *args, b=7):
        return [a, args, b]

    # Since Python 3.13.3, the TypeError message for missing positional-only arguments has changed.
    # See: https://github.com/python/cpython/pull/130192
    with pytest.raises(TypeError, match=r"missing .* argument: 'a'"):
        relaxed_call(f4, a=2, b=7)

    def f5(a, *args, b=7, **kwargs):
        return [a, args, b, kwargs]

    assert relaxed_call(f5, 1, 2, 3, 4, b=7, c=9) == [1, (2, 3, 4), 7, {"c": 9}]


def test_relaxed_wrap():
    from pyodide.code import relaxed_wrap

    with pytest.raises(TypeError, match="Cannot wrap function"):
        relaxed_wrap(int)

    @relaxed_wrap
    def f1(a, b):
        return [a, b]

    assert f1(1, 2) == [1, 2]
    assert f1(1, 2, 3) == [1, 2]
    assert f1(1, b=7) == [1, 7]
    assert f1(a=2, b=7) == [2, 7]
    assert f1(1, b=7, c=9) == [1, 7]
    assert f1(1, 2, 3, c=9) == [1, 2]
    with pytest.raises(TypeError, match="missing a required argument: 'b'"):
        f1(1)
    with pytest.raises(TypeError, match="multiple values for argument 'b'"):
        f1(1, 2, b=3)

    @relaxed_wrap
    def f2(a, b=7):
        return [a, b]

    assert f2(1, 2) == [1, 2]
    assert f2(1, 2, 3) == [1, 2]
    assert f2(1, b=7) == [1, 7]
    assert f2(a=2, b=7) == [2, 7]
    assert f2(1, b=7, c=9) == [1, 7]
    assert f2(1, 2, 3, c=9) == [1, 2]
    assert f2(1) == [1, 7]
    with pytest.raises(TypeError, match="missing a required argument: 'a'"):
        f2()

    @relaxed_wrap
    def f3(a, *args, b=7):
        return [a, args, b]

    assert f3(1, 2) == [1, (2,), 7]
    assert f3(1, 2, 3) == [1, (2, 3), 7]
    assert f3(1, b=7) == [1, (), 7]
    assert f3(a=2, b=7) == [2, (), 7]
    assert f3(1, b=7, c=9) == [1, (), 7]
    assert f3(1, 2, 3, c=9) == [1, (2, 3), 7]
    assert f3(1) == [1, (), 7]

    @relaxed_wrap
    def f4(a, /, *args, b=7):
        return [a, args, b]

    with pytest.raises(TypeError, match=r"missing .* argument: 'a'"):
        f4(a=2, b=7)

    @relaxed_wrap
    def f5(a, *args, b=7, **kwargs):
        return [a, args, b, kwargs]

    assert f5(1, 2, 3, 4, b=7, c=9) == [1, (2, 3, 4), 7, {"c": 9}]


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
            def eval_code(code, globals=None, locals=None):
                return [globals["x"], old_eval_code(code, globals, locals)]
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


def test_promise_check(selenium):
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
        assert selenium.run_js(f"return pyodide._api.isPromise({s}) === false;")

    if not selenium.browser == "node":
        assert selenium.run_js("return pyodide._api.isPromise(document.all) === false;")

    assert selenium.run_js("return pyodide._api.isPromise(Promise.resolve()) === true;")

    assert selenium.run_js(
        """
        return pyodide._api.isPromise(new Promise((resolve, reject) => {}));
        """
    )

    assert not selenium.run_js(
        """
        let d = pyodide.runPython("{}");
        try {
            return pyodide._api.isPromise(d);
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
            resp = await fetch("pyodide-lock.json")
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
            assert sys.last_exc is x
            assert sys.last_value is x
            assert sys.last_type is type(x)
            assert sys.last_traceback is x.__traceback__
        `);
        """
    )


def test_check_interrupt(selenium):
    # First make sure checkInterrupt works when interrupt buffer is undefined.
    # It should just do nothing in this case.
    selenium.run_js(
        """
        pyodide.setInterruptBuffer(undefined);
        pyodide.checkInterrupt();
        """
    )

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
                try:
                    test();
                finally:
                    del test
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


def test_check_interrupt_no_gil(selenium):
    """Check interrupt has a special case for GIL not held.
    Make sure that it works.
    """
    selenium.run_js(
        """
        // release GIL
        const tstate = pyodide._module._PyEval_SaveThread();

        try {
            // check that checkInterrupt works when interrupt buffer not defined
            // it should do nothing.
            pyodide.setInterruptBuffer(undefined);
            pyodide.checkInterrupt();
            ib = new Int32Array(1);
            pyodide.setInterruptBuffer(ib);
            pyodide.checkInterrupt();

            ib[0] = 2;
            let err;
            try {
                pyodide.checkInterrupt();
            } catch(e) {
                err = e;
            }
            assert(() => err instanceof pyodide.FS.ErrnoError);
            assert(() => err.errno === pyodide.ERRNO_CODES.EINTR);
            assert(() => ib[0] === 2);
            ib[0] = 0;
        } finally {
            // acquire GIL
            pyodide._module._PyEval_RestoreThread(tstate)
        }
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


@pytest.mark.xfail_browsers(node="No DOMException in node")
@run_in_pyodide
def test_run_python_dom_error(selenium):
    import pytest

    from js import DOMException
    from pyodide.ffi import JsException

    with pytest.raises(JsException, match="oops"):
        raise DOMException.new("oops")


def test_run_python_locals(selenium):
    selenium.run_js(
        """
        let dict = pyodide.globals.get("dict");
        let locals = dict([["x", 7]]);
        let globals = dict([["x", 5], ["y", 29]]);
        dict.destroy();
        let result = pyodide.runPython("z = 13; x + y", {locals, globals});
        assert(() => locals.get("z") === 13);
        assert(() => locals.has("x"));
        let result2 = pyodide.runPython("del x; x + y", {locals, globals});
        assert(() => !locals.has("x"));
        assert(() => result === 7 + 29);
        assert(() => result2 === 5 + 29);
        locals.destroy();
        globals.destroy();
        """
    )


@run_in_pyodide
def test_create_once_callable(selenium):
    import sys

    from pytest import raises

    from pyodide.code import run_js
    from pyodide.ffi import JsException, create_once_callable

    destroyed = False

    class Square:
        def __call__(self, x):
            return x * x

        def __del__(self):
            nonlocal destroyed
            destroyed = True

    f = Square()
    assert sys.getrefcount(f) == 2
    proxy = create_once_callable(f)
    assert sys.getrefcount(f) == 3

    call7 = run_js("(f) => f(7)")
    assert call7(proxy) == 49
    assert sys.getrefcount(f) == 2
    with raises(JsException, match="can only be called once"):
        call7(proxy)
    del f
    assert destroyed


@run_in_pyodide
def test_create_proxy(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import create_proxy

    [testAddListener, testCallListener, testRemoveListener] = run_js(
        """
        function testAddListener(f){
            self.listener = f;
        }
        function testCallListener(f){
            return self.listener();
        }
        function testRemoveListener(f){
            return self.listener === f;
        }
        [testAddListener, testCallListener, testRemoveListener]
        """
    )

    destroyed = False

    class Test:
        def __call__(self):
            return 7

        def __del__(self):
            nonlocal destroyed
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
    assert destroyed


@run_in_pyodide
def test_create_proxy_capture_this(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import create_proxy

    o = run_js("({})")

    def f(self):
        assert self == o

    o.f = create_proxy(f, capture_this=True)
    run_js("(o) => { o.f(); o.f.destroy(); }")(o)


@run_in_pyodide
def test_create_proxy_roundtrip(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import JsDoubleProxy, create_proxy

    f = {}  # type: ignore[var-annotated]
    o = run_js("({})")
    o.f = create_proxy(f, roundtrip=True)
    assert isinstance(o.f, JsDoubleProxy)
    assert o.f.unwrap() is f
    o.f.destroy()
    o.f = create_proxy(f, roundtrip=False)
    assert o.f is f
    run_js("(o) => { o.f.destroy(); }")(o)


@run_in_pyodide
def test_return_destroyed_value(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException, create_proxy

    f = run_js("(function(x){ return x; })")
    p = create_proxy([])  # type: ignore[var-annotated]
    p.destroy()
    with pytest.raises(JsException, match="Object has already been destroyed"):
        f(p)


def test_docstrings_a():
    from _pyodide._core_docs import _instantiate_token
    from _pyodide.docstring import dedent_docstring, get_cmeth_docstring
    from pyodide.ffi import JsPromise

    jsproxy: JsPromise[Any] = JsPromise(_instantiate_token)
    c_docstring = get_cmeth_docstring(jsproxy.then)
    assert (
        c_docstring
        == "then(onfulfilled, onrejected=None)\n--\n\n"
        + dedent_docstring(jsproxy.then.__doc__)
    )


def test_docstrings_b(selenium):
    from _pyodide._core_docs import _instantiate_token
    from _pyodide.docstring import dedent_docstring
    from pyodide.ffi import JsPromise, create_once_callable

    jsproxy: JsPromise[Any] = JsPromise(_instantiate_token)
    ds_then_should_equal = dedent_docstring(jsproxy.then.__doc__)
    sig_then_should_equal = "(onfulfilled, onrejected=None)"
    ds_once_should_equal = dedent_docstring(create_once_callable.__doc__)
    sig_once_should_equal = "(obj, /, *, _may_syncify=False)"
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


@pytest.mark.xfail_browsers(safari="TODO: traceback is not the same on Safari")
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
        # Remove ANSI color codes
        x = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", x)
        x = re.sub("\n.*site-packages.*", "", x)
        x = re.sub("/lib/python.*/", "", x)
        x = re.sub("/lib/python.*/", "", x)
        x = re.sub("warning: no [bB]lob.*\n", "", x)
        x = re.sub("Error: intentionally triggered fatal error!\n", "", x)
        x = re.sub(" +at .*\n", "", x)
        x = re.sub(".*@https?://[0-9.:]*/.*\n", "", x)
        x = re.sub(".*@debugger.*\n", "", x)
        x = re.sub(".*@chrome.*\n", "", x)
        x = re.sub("line [0-9]*", "line xxx", x)
        x = x.replace("\n\n", "\n")
        return x

    err_msg = strip_stack_trace(selenium_standalone.logs)
    err_msg = "".join(strip_assertions_stderr(err_msg.splitlines(keepends=True)))
    assert (
        err_msg
        == dedent(
            strip_stack_trace(
                """
                Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.
                The cause of the fatal error was:
                Stack (most recent call first):
                  File "<exec>", line 8 in h
                  File "<exec>", line 6 in g
                  File "<exec>", line 4 in f
                  File "<exec>", line 9 in <module>
                  File "/lib/pythonxxx/pyodide/_base.py", line 242 in run
                  File "/lib/pythonxxx/pyodide/_base.py", line 344 in eval_code
                """
            )
        ).strip()
    )
    selenium_standalone.run_js(
        """
        assertThrows(() => pyodide.runPython, "Error", "Pyodide already fatally failed and can no longer be used.")
        assertThrows(() => pyodide.globals, "Error", "Pyodide already fatally failed and can no longer be used.")
        """
    )


@pytest.mark.skip_refcount_check
def test_exit_error(selenium_standalone):
    x = selenium_standalone.run_js(
        """
        try {
            pyodide.runPython(`
                import os
                def f():
                    g()
                def g():
                    h()
                def h():
                    os._exit(0)
                f()
            `);
        } catch(e){
            return e.toString();
        }
        """
    )
    assert x == "Exit: Program terminated with exit(0)"


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


@pytest.mark.xfail_browsers(safari="TODO: traceback is not exactly the same on Safari")
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
            if re.fullmatch(r"\:[0-9]*", file) or file in {
                "debugger eval code",
                "evalmachine.<anonymous>",
            }:
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
        ["_pyodide/_base.py", "pyimport_impl"],
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
                assert e == sys.last_exc
                assert e == sys.last_value
            finally:
                del err
            assert sys.getrefcount(sys.last_exc) == 3
        `);
        """
    )


def test_env(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    hashval = selenium.run_js(
        """
        let pyodide = await loadPyodide({
            env : {PYTHONHASHSEED : 1},
        });
        return pyodide.runPython(`
            hash((1,2,3))
        `)
        """
    )
    # This may need to be updated when the Python version changes.
    assert hashval == -2022708474


def test_version_variable(selenium):
    js_version = selenium.run_js(
        """
        return pyodide.version
        """
    )

    core_version = selenium.run_js(
        """
        return pyodide._api.version
        """
    )

    from pyodide import __version__ as py_version

    assert js_version == py_version == core_version


def test_abiVersion_variable(selenium):
    core_abi_version = selenium.run_js(
        """
        return pyodide._api.abiVersion
        """
    )

    lockfile_abi_version = selenium.run_js(
        """
        return pyodide._api.lockfile_info.abi_version
        """
    )

    py_abi_version = selenium.run(
        """
        from sysconfig import get_config_var

        get_config_var("PYODIDE_ABI_VERSION")
        """
    )

    assert lockfile_abi_version == py_abi_version == core_abi_version


@run_in_pyodide
def test_default_sys_path(selenium):
    import sys
    from sys import version_info

    major = version_info[0]
    minor = version_info[1]
    prefix = sys.prefix
    platlibdir = sys.platlibdir
    paths = [
        f"{prefix}{platlibdir}/python{major}{minor}.zip",
        f"{prefix}{platlibdir}/python{major}.{minor}",
        f"{prefix}{platlibdir}/python{major}.{minor}/lib-dynload",
        f"{prefix}{platlibdir}/python{major}.{minor}/site-packages",
    ]

    for path in paths:
        assert path in sys.path


@run_in_pyodide
def test_sys_path0(selenium):
    import sys

    assert sys.path[0] == ""


@pytest.mark.requires_dynamic_linking
def test_fullstdlib(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        let pyodide = await loadPyodide({
            fullStdLib: true,
        });

        await pyodide.loadPackage("micropip");

        pyodide.runPython(`
            import pyodide_js
            import micropip
            loaded_packages = micropip.list()
            assert all((lib in micropip.list()) for lib in pyodide_js._api.lockfile_unvendored_stdlibs)
        `);
        """
    )


def test_loadPyodide_relative_index_url(selenium_standalone_noload):
    """Check that loading Pyodide with a relative URL works"""
    selenium_standalone_noload.run_js(
        """
        self.pyodide = await loadPyodide({ indexURL: "./" });
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
    from js import x  # type: ignore[attr-defined]

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
def test_module_not_found_note(selenium_standalone):
    import importlib

    import pytest

    from _pyodide._importhook import add_note_to_module_not_found_error
    from pyodide.code import run_js

    unvendored_stdlibs = ["test"]
    removed_stdlibs = ["pwd", "turtle", "tkinter"]
    lockfile_packages = [
        "micropip",
    ]

    # When error is wrapped, add_note_to_module_not_found_error is called
    with pytest.raises(ModuleNotFoundError) as e:
        run_js("(f) => f()")(lambda: importlib.import_module("test"))
    assert "unvendored from the Python standard library" in e.value.__notes__[0]
    assert len(e.value.__notes__) == 1

    for lib in unvendored_stdlibs:
        with pytest.raises(ModuleNotFoundError) as e:
            importlib.import_module(lib)
        add_note_to_module_not_found_error(e.value)
        add_note_to_module_not_found_error(e.value)
        assert "unvendored from the Python standard library" in e.value.__notes__[0]
        assert len(e.value.__notes__) == 1

    for lib in removed_stdlibs:
        with pytest.raises(ModuleNotFoundError) as e:
            importlib.import_module(lib)
        add_note_to_module_not_found_error(e.value)
        assert "removed from the Python standard library" in e.value.__notes__[0]

    with pytest.raises(ModuleNotFoundError, match="No module named"):
        importlib.import_module("urllib.there_is_no_such_module")

    for lib in lockfile_packages:
        with pytest.raises(
            ModuleNotFoundError,
        ) as e:
            importlib.import_module(lib)
        add_note_to_module_not_found_error(e.value)
        assert "included in the Pyodide distribution" in e.value.__notes__[0]

    with pytest.raises(ModuleNotFoundError, match="No module named") as e:
        importlib.import_module("pytest.there_is_no_such_module")
    add_note_to_module_not_found_error(e.value)
    assert getattr(e.value, "__notes__", None) is None

    # liblzma and openssl are libraries not python packages, so it should just fail.
    for pkg in ["liblzma", "openssl"]:
        with pytest.raises(ModuleNotFoundError, match="No module named") as e:
            importlib.import_module(pkg)
        add_note_to_module_not_found_error(e.value)
        assert getattr(e.value, "__notes__", None) is None


@run_in_pyodide
def test_importhook_called_from_pytest(selenium):
    """
    Whenever importlib itself resolves `import a.b`, it splits on the . and
    first imports `a` and then `a.b`. However, pytest does not, it calls
    `find_spec("a.b")` directly here:
    https://github.com/pytest-dev/pytest/blob/ea0fa639445ae08616edd2c15189a1a76168f018/src/_pytest/pathlib.py#L693-L698

    This previously could lead to KeyError being raised in `JsFinder`.
    """
    import sys

    def _import_module_using_spec(module_name):
        """Modeled on a fragment of _pytest.pathlib._import_module_using_spec"""
        for meta_importer in sys.meta_path:
            meta_importer.find_spec(module_name, [])

    # Assertion: This should not raise KeyError.
    _import_module_using_spec("a.b")


@run_in_pyodide
def test_windows_to_linux_path_finder(selenium):
    from pathlib import Path

    from _pyodide._importhook import WindowsToLinuxPathFinder

    # not using tempfile for readability
    tmp_dir = Path("/tmp/my/temporary/directory/for/testing")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    module_file = tmp_dir / "test_module.py"

    # should not exist yet
    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["C:\\my\\temporary\\directory\\for\\testing"]
    )
    assert spec is None

    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["C://my//temporary//directory//for//testing"]
    )
    assert spec is None

    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["/tmp/my/temporary/directory/for/testing"]
    )
    assert spec is None

    module_file.write_text("TEST_VALUE = 123")

    # now it should be found
    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["C:\\tmp\\my\\temporary\\directory\\for\\testing"]
    )
    assert spec is not None

    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["C://tmp//my//temporary//directory//for//testing"]
    )
    assert spec is not None

    # This finder should not care about non-Windows paths
    spec = WindowsToLinuxPathFinder.find_spec(
        "test_module", ["/tmp/my/temporary/directory/for/testing"]
    )
    assert spec is None

    spec = WindowsToLinuxPathFinder.find_spec(
        "non_existent_module", ["C:\\tmp\\my\\temporary\\directory\\for\\testing"]
    )
    assert spec is None

    # cleanup
    module_file.unlink()
    tmp_dir.rmdir()


@run_in_pyodide
def test_windows_to_linux_path_finder_edge_cases(selenium):
    """Test edge cases for WindowsToLinuxPathFinder."""
    from _pyodide._importhook import WindowsToLinuxPathFinder

    # Empty path list
    spec = WindowsToLinuxPathFinder.find_spec("test_module", [])
    assert spec is None

    # None path (should use sys.path, but all conversions might fail)
    spec = WindowsToLinuxPathFinder.find_spec("test_module", None)
    assert spec is None

    # zipimport path
    spec = WindowsToLinuxPathFinder.find_spec("test_module", ["my_whl.whl"])
    assert spec is None


@run_in_pyodide
def test_windows_to_linux_path_import(selenium_standalone):
    import sys
    from pathlib import Path

    tmp_dir = Path("/tmp/my/temporary/directory/for/testing/import")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    module_file = tmp_dir / "test_module.py"

    sys.path.append("C:\\tmp\\my\\temporary\\directory\\for\\testing\\import")

    try:
        import test_module

        raise AssertionError("Module should not be found yet")
    except ModuleNotFoundError:
        pass

    module_file.write_text("TEST_VALUE = 456")

    import test_module

    assert test_module.TEST_VALUE == 456

    # cleanup
    module_file.unlink()
    tmp_dir.rmdir()


def test_args(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    assert selenium.run_js(
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
            stdout,
            stderr,
            args: ['-c', 'print([x*x+1 for x in range(10)])'],
            env: { PYTHONINSPECT: "" },
        });
        self.pyodide = pyodide;
        globalThis.pyodide = pyodide;
        pyodide._module._run_main();
        return stdoutStrings.pop()
        """
    ) == repr([x * x + 1 for x in range(10)])


def test_args_OO(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    doc = selenium.run_js(
        """
        let pyodide = await loadPyodide({
            args: ['-OO']
        });
        pyodide.runPython(`import sys; sys.__doc__`)
        """
    )

    assert not doc


@pytest.mark.xfail_browsers(chrome="Node only", firefox="Node only", safari="Node only")
def test_relative_index_url(selenium, tmp_path):
    tmp_dir = Path(tmp_path)
    subprocess.run(["node", "-v"], encoding="utf8", check=True)

    shutil.copy(PYODIDE_ROOT / "dist/pyodide.js", tmp_dir / "pyodide.js")

    result = subprocess.run(
        [
            "node",
            "-e",
            rf"""
            const loadPyodide = require("{tmp_dir / "pyodide.js"}").loadPyodide;
            async function main(){{
                py = await loadPyodide({{indexURL: "./dist"}});
                console.log("\n");
                console.log(py._module.API.config.indexURL);
            }}
            main();
            """,
        ],
        cwd=PYODIDE_ROOT,
        capture_output=True,
        encoding="utf8",
        check=False,
    )
    import textwrap

    def print_result(result):
        if result.stdout:
            print("  stdout:")
            print(textwrap.indent(result.stdout, "    "))
        if result.stderr:
            print("  stderr:")
            print(textwrap.indent(result.stderr, "    "))

    if result.returncode:
        print_result(result)
        result.check_returncode()

    try:
        assert result.stdout.strip().split("\n")[-1] == str(DIST_PATH) + "/"
    finally:
        print_result(result)


@pytest.mark.xfail_browsers(chrome="Node only", firefox="Node only", safari="Node only")
def test_index_url_calculation_source_map(selenium):
    import os

    node_options = ["--enable-source-maps"]

    result = subprocess.run(
        ["node", "-v"], capture_output=True, encoding="utf8", check=True
    )

    DIST_DIR = str(Path.cwd() / "dist")

    env = os.environ.copy()
    env["DIST_DIR"] = DIST_DIR
    result = subprocess.run(
        [
            "node",
            *node_options,
            "-e",
            """
            const { loadPyodide } = require(`${process.env.DIST_DIR}/pyodide`);
            async function main() {
                const py = await loadPyodide();
                console.log("indexURL:", py._module.API.config.indexURL);
            }
            main();
            """,
        ],
        env=env,
        capture_output=True,
        encoding="utf8",
        check=False,
    )

    assert f"indexURL: {DIST_DIR}" in result.stdout


@pytest.mark.xfail_browsers(chrome="Node only", firefox="Node only", safari="Node only")
@pytest.mark.parametrize(
    "filename, import_stmt",
    [
        ("index.js", "const { loadPyodide } = require('%s/pyodide.js')"),  # commonjs
        ("index.mjs", "import { loadPyodide } from '%s/pyodide.mjs'"),  # esm
    ],
)
def test_default_index_url_calculation_node(selenium, tmp_path, filename, import_stmt):
    Path(tmp_path / filename).write_text(
        (import_stmt % DIST_PATH)
        + "\n"
        + """
        async function main() {
            const py = await loadPyodide();
            console.log("indexURL:", py._module.API.config.indexURL);
        }
        main();
        """
    )

    result = subprocess.run(
        [
            "node",
            filename,
        ],
        capture_output=True,
        encoding="utf8",
        cwd=tmp_path,
        check=False,
    )

    assert f"indexURL: {DIST_PATH}" in result.stdout


@pytest.mark.xfail_browsers(
    node="Browser only", safari="Safari doesn't support wasm-unsafe-eval"
)
def test_csp(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    target_path = DIST_PATH / "test_csp.html"
    try:
        shutil.copy(PYODIDE_ROOT / "src/templates/test_csp.html", target_path)
        selenium.goto(f"{selenium.base_url}/test_csp.html")
        selenium.javascript_setup()
        selenium.load_pyodide()
    finally:
        target_path.unlink()


@pytest.mark.xfail_browsers(node="static import test is browser-only")
def test_static_import(selenium_standalone_noload, tmp_path, httpserver):
    selenium = selenium_standalone_noload

    # copy dist to tmp_path to perform file changes safely
    shutil.copytree(DIST_PATH, tmp_path, dirs_exist_ok=True)

    # define the directory to hide the statically imported pyodide.asm.js in
    hiding_dir = "hide_pyodide_asm_for_test"

    # create the directory and move pyodide.asm.js to the directory
    # so that dynamic import won't find it
    (tmp_path / hiding_dir).mkdir()
    shutil.move(tmp_path / "pyodide.asm.js", tmp_path / hiding_dir / "pyodide.asm.js")

    # make sure the test html references the new directory when importing pyodide.asm.js
    test_html = (
        PYODIDE_ROOT / "src/templates/module_static_import_test.html"
    ).read_text()
    test_html = test_html.replace("./pyodide.asm.js", f"./{hiding_dir}/pyodide.asm.js")
    test_html_content = test_html.encode()

    # Setup httpserver to serve all necessary files
    httpserver.expect_oneshot_request(
        "/module_static_import_test.html"
    ).respond_with_data(
        test_html_content,
        content_type="text/html",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )

    # Serve the moved pyodide.asm.js file
    pyodide_asm_data = (tmp_path / hiding_dir / "pyodide.asm.js").read_bytes()
    httpserver.expect_oneshot_request(
        f"/{hiding_dir}/pyodide.asm.js"
    ).respond_with_data(
        pyodide_asm_data,
        content_type="application/javascript",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )

    # Serve other necessary pyodide files
    for file_name in [
        "pyodide.js",
        "pyodide.mjs",
        "pyodide-lock.json",
        "python_stdlib.zip",
        "pyodide.asm.wasm",
    ]:
        file_path = tmp_path / file_name
        if file_path.exists():
            file_data = file_path.read_bytes()
            content_type = (
                "application/javascript"
                if file_name.endswith((".js", ".mjs"))
                else (
                    "application/json"
                    if file_name.endswith(".json")
                    else "application/zip"
                    if file_name.endswith(".zip")
                    else "application/wasm"
                    if file_name.endswith(".wasm")
                    else "application/octet-stream"
                )
            )
            httpserver.expect_request(f"/{file_name}").respond_with_data(
                file_data,
                content_type=content_type,
                headers={"Access-Control-Allow-Origin": "*"},
                status=200,
            )

    url = httpserver.url_for("/module_static_import_test.html")
    selenium.goto(url)
    selenium.javascript_setup()
    selenium.load_pyodide()
    selenium.run_js(
        """
        pyodide.runPython(`
            print('Static import works')
        `);
        """
    )


def test_python_error(selenium):
    [msg, ty] = selenium.run_js(
        """
        try {
            pyodide.runPython("raise TypeError('oops')");
        } catch(e) {
            return [e.message, e.type];
        }
        """
    )
    assert msg.endswith("TypeError: oops\n")
    assert ty == "TypeError"


def test_python_version(selenium):
    selenium.run_js(
        """
        sys = pyodide.pyimport("sys");
        const [major, minor, micro] = pyodide._api.pyVersionTuple;
        assert(() => sys.version_info.major === major);
        assert(() => sys.version_info.minor === minor);
        assert(() => sys.version_info.micro === micro);
        sys.destroy();
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_custom_python_stdlib_URL(selenium_standalone_noload, runtime):
    selenium = selenium_standalone_noload
    stdlib_target_path = DIST_PATH / "python_stdlib2.zip"
    shutil.copy(DIST_PATH / "python_stdlib.zip", stdlib_target_path)

    try:
        selenium.run_js(
            """
            let pyodide = await loadPyodide({
                fullStdLib: false,
                stdLibURL: "./python_stdlib2.zip",
            });
            // Check that we can import stdlib library modules
            let statistics = pyodide.pyimport('statistics');
            assert(() => statistics.median([2, 3, 1]) === 2)
            """
        )
    finally:
        stdlib_target_path.unlink()


def test_pickle_internal_error(selenium):
    @run_in_pyodide
    def helper(selenium):
        from pyodide.ffi import InternalError

        raise InternalError("oops!")

    from pyodide.ffi import InternalError

    with pytest.raises(InternalError):
        helper(selenium)


@pytest.mark.parametrize(
    "run_python", ["pyodide.runPython", "await pyodide.runPythonAsync"]
)
def test_runpython_filename(selenium, run_python):
    msg = selenium.run_js(
        """
        try {
            %s(`
                def f1():
                    f2()

                def f2():
                    raise Exception("oops")

                f1()
            `, {filename: "a.py"});
        } catch(e) {
            return e.message
        }
        """
        % run_python
    )
    expected = dedent(
        """\
        File "a.py", line 3, in f1
          f2()

        File "a.py", line 6, in f2
          raise Exception("oops")
          ^^^^^^^^^^^^^^^
        """
    ).strip()

    assert dedent("\n".join(msg.splitlines()[-7:-1])) == expected
    msg = selenium.run_js(
        """
        let f1;
        try {
            f1 = pyodide.globals.get("f1");
            f1();
        } catch(e) {
            console.log(e);
            return e.message;
        } finally {
            f1.destroy();
        }
        """
    )
    assert dedent("\n".join(msg.splitlines()[1:-1])) == expected


@pytest.mark.requires_dynamic_linking
@run_in_pyodide
def test_hiwire_invalid_ref(selenium):
    import pytest

    import pyodide_js
    from pyodide.code import run_js
    from pyodide.ffi import JsException

    _hiwire_get = pyodide_js._module._hiwire_get
    _hiwire_incref = pyodide_js._module._hiwire_incref
    _hiwire_decref = pyodide_js._module._hiwire_decref
    _api = pyodide_js._api

    _hiwire_incref(0)
    assert not _api.fail_test
    _hiwire_decref(0)
    assert not _api.fail_test
    expected = r"Pyodide internal error: Argument to hiwire_get is falsy \(but error indicator is not set\)\."
    with pytest.raises(JsException, match=expected):
        _hiwire_get(0)
    assert _api.fail_test
    _api.fail_test = False

    with pytest.raises(AssertionError, match="This is a message"):
        run_js(
            """
            const msgptr = pyodide._module.stringToNewUTF8("This is a message");
            const AssertionError = pyodide._module.HEAP32[pyodide._module._PyExc_AssertionError/4];
            pyodide._module._PyErr_SetString(AssertionError, msgptr);
            pyodide._module._free(msgptr);
            try {
                pyodide._module._hiwire_get(0);
            } finally {
                pyodide._module._PyErr_Clear();
            }
            """
        )
    msg = "hiwire_{} on invalid reference 77. This is most likely due to use after free. It may also be due to memory corruption."
    with pytest.raises(JsException, match=msg.format("get")):
        _hiwire_get(77)
    assert _api.fail_test
    _api.fail_test = False
    with pytest.raises(JsException, match=msg.format("incref")):
        _hiwire_incref(77)
    assert _api.fail_test
    _api.fail_test = False
    with pytest.raises(JsException, match=msg.format("decref")):
        _hiwire_decref(77)
    assert _api.fail_test
    _api.fail_test = False


def test_system_exit(selenium):
    """Make sure nothing weird happens when we throw SystemExit"""
    for _ in range(3):
        selenium.run_js(
            """
            assertThrows(
                () =>
                    pyodide.runPython(`
                        exit(1)
                    `),
                "PythonError",
                "SystemExit: 1",
            );
            """
        )


@run_in_pyodide
async def test_bug_4861(selenium):
    """In version 0.26.1, there was a regression that makes this raise
    "KeyError: '__builtins__'".

    I don't really understand what this reproducer does, what the problem was,
    or why the fix prevents the problem.
    """
    import collections

    from pyodide.code import run_js

    class ChainMap(collections.ChainMap, dict):  # type:ignore[misc, type-arg]
        pass

    def g(x):
        return eval("x()", ChainMap({}, {"x": x}))

    await g(run_js("async () => {}"))


@run_in_pyodide
def test_lockfile_api(selenium):
    from pyodide_js import lockfile

    lockfile_info = lockfile.info
    lockfile_packages = lockfile.packages

    assert lockfile_info is not None
    assert lockfile_info.abi_version is not None
    assert lockfile_info.version is not None
    assert lockfile_info.python is not None

    assert lockfile_packages.micropip is not None


def test_fs_init(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    res = selenium.run_js(
        """
        let pyodide = await loadPyodide({
            async fsInit(FS, {sitePackages}) {
                await sleep(20);
                FS.writeFile(sitePackages + "/blah.pth", "foo\\nbar\\nbletch");
                FS.mkdir(sitePackages + "/foo");
                FS.mkdir(sitePackages + "/bar");
            }
        });
        return pyodide.runPython(`import sys; sys.path`).toJs();
        """
    )
    # This may need to be updated when the Python version changes.
    assert res[-2].endswith("site-packages/foo")
    assert res[-1].endswith("site-packages/bar")


def test_compat_null_to_none(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    doc = selenium.run_js(
        """
        let pyodide = await loadPyodide({
            convertNullToNone: true
        });
        pyodide.runPython(`
            from pyodide.code import run_js

            assert run_js("null") == None
        `);
        """
    )

    assert not doc
