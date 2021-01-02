import ast
from copy import deepcopy
from pathlib import Path
import sys
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

from pyodide import find_imports, eval_code  # noqa: E402
from pyodide._base import _adjust_ast_to_store_result

import pytest


def test_find_imports():

    res = find_imports(
        dedent(
            """
           import six
           import numpy as np
           from scipy import sparse
           import matplotlib.pyplot as plt
           """
        )
    )
    assert set(res) == {"numpy", "scipy", "six", "matplotlib"}


def test_adjust_ast():
    target_name = "<EXEC-LAST-EXPRESSION>"

    def helper(code):
        code = dedent(code)
        mod = ast.parse(code)
        return [mod, _adjust_ast_to_store_result(target_name, deepcopy(mod), code)]

    def assert_stored_last_line(code):
        [mod, adjusted_mod] = helper(code)
        assert (
            ast.dump(adjusted_mod.body[-1].targets[0])
            == f"Name(id='{target_name}', ctx=Store())"
        )
        assert ast.dump(adjusted_mod.body[-1].value) == ast.dump(mod.body[-1].value)
        mod.body.pop()
        adjusted_mod.body.pop()
        assert ast.dump(mod) == ast.dump(adjusted_mod)

    def assert_stored_none(code):
        [mod, adjusted_mod] = helper(code)
        assert (
            ast.dump(adjusted_mod.body[-1].targets[0])
            == f"Name(id='{target_name}', ctx=Store())"
        )
        assert (
            ast.dump(adjusted_mod.body[-1].value) == "Constant(value=None, kind=None)"
        )
        adjusted_mod.body.pop()
        assert ast.dump(mod) == ast.dump(adjusted_mod)

    assert_stored_last_line("1+1")
    assert_stored_last_line("await 1+1")
    assert_stored_last_line("print(2)")
    assert_stored_last_line("(x:=4)")

    assert_stored_none("x=4")
    assert_stored_none("1+1;")
    assert_stored_none("def f(): 4")
    assert_stored_none(
        """
        def f():
            print(9)
            return 2*7 + 5
    """
    )

    assert_stored_last_line(
        """
        def f(x):
            print(9)
            return 2*x + 5
        f(77)
    """
    )


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

    assert eval_code("1+1;", ns) is None


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
        pyodide.mountPackage("a", a);
        pyodide.mountPackage("b", b);
        return pyodide.runPython(`
            from a import x
            from b import x as x2
            result = [x(), x2()]
            import a
            import b
            result += [a.s, dir(a), dir(b)]
            result
        `)
        """
    )
    assert result[:3] == ["x1", "x2", 3]
    assert set([x for x in result[3] if len(x) == 1]) == set(["x", "y", "s", "t"])
    assert set([x for x in result[4] if len(x) == 1]) == set(["x", "y", "u", "t"])


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
        pyodide.mountPackage("a", a);
        pyodide.mountPackage("b", b);
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
    assert set(result[3]) == set(
        [
            "x", "y", "s", "t",
            "__dir__", "__doc__", "__getattr__", "__loader__",
            "__name__", "__package__", "__spec__",
            "jsproxy",
        ]
    )
    # fmt: on
    assert set([x for x in result[4] if not x.startswith("__")]) == set(
        ["x", "y", "u", "t", "jsproxy"]
    )


def test_mount_errors(selenium):
    selenium.run_js(
        """
        let a = new Map(Object.entries({ s : 7 }));
        let b = new Map(Object.entries({ t : 3 }));
        pyodide.mountPackage("a", a);
        pyodide.mountPackage("a", b);
        pyodide.dismountPackage("a")
        pyodide.runPython(`
            try:
                import a
                assert False
            except ImportError:
                pass
        `)
        """
    )
    selenium.run_js(
        """
        try {
            pyodide.dismountPackage("doesnotexist");
            throw new Error("dismountPackage should have thrown an error.");
        } catch(e){
            if(!e.message.includes("Cannot dismount module 'doesnotexist': no such module exists.")){
                throw e;
            }
        }
        pyodide.runPython("import pathlib")
        try {
            pyodide.dismountPackage("pathlib");
            throw new Error("dismountPackage should have thrown an error.");
        } catch(e){
            if(!e.message.includes("was not mounted with 'pyodide.mountPackage'")){
                throw e;
            }
        }
        try {
            pyodide.mountPackage("pathlib", {});
            throw new Error("dismountPackage should have thrown an error.");
        } catch(e){
            if(!e.message.includes("was not mounted with 'pyodide.mountPackage'")){
                throw e;
            }
        }
        """
    )


@pytest.mark.xfail
def test_window_invocation(selenium):
    """ Make sure js.setTimeout etc don't yeild illegal invocation errors. """
    selenium.run(
        """
        import js
        def temp():
            print("okay?")
        js.setTimeout(temp, 100)
        js.fetch("example.com")
        """
    )
