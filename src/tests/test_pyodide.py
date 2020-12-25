import ast
from copy import deepcopy
from pathlib import Path
import sys
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

from pyodide import find_imports, eval_code  # noqa: E402
from pyodide._base import _adjust_ast_to_store_result


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
