import pytest
from pathlib import Path
import sys
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

from pyodide import find_imports, eval_code  # noqa: E402
from pyodide._base import CodeRunner  # noqa: E402


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
    runner = CodeRunner()
    assert runner.quiet("1+1;")
    assert not runner.quiet("1+1#;")
    assert not runner.quiet("5-2  # comment with trailing semicolon ;")
    assert runner.run("4//2\n") == 2
    assert runner.run("4//2;") is None
    assert runner.run("x = 2\nx") == 2
    assert runner.run("def f(x):\n    return x*x+1\n[f(x) for x in range(6)]") == [
        1,
        2,
        5,
        10,
        17,
        26,
    ]

    # with 'quiet_trailing_semicolon' set to False
    runner = CodeRunner(quiet_trailing_semicolon=False)
    assert not runner.quiet("1+1;")
    assert not runner.quiet("1+1#;")
    assert not runner.quiet("5-2  # comment with trailing semicolon ;")
    assert runner.run("4//2\n") == 2
    assert runner.run("4//2;") == 2


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
        assert not selenium.run_js(f"return pyodide._module.hiwire.isPromise({s})")

    assert selenium.run_js(
        "return pyodide._module.hiwire.isPromise(Promise.resolve());"
    )

    assert selenium.run_js(
        """
        return pyodide._module.hiwire.isPromise(new Promise((resolve, reject) => {}));
        """
    )

    assert not selenium.run_js(
        """
        return pyodide._module.hiwire.isPromise(pyodide.globals);
        """
    )


def test_keyboard_interrupt(selenium):
    assert selenium.run_js(
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
        return pyodide.runPython(`
            2000 < x < 2500
        `)
        """
    )
