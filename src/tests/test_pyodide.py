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

    # default mode ('last_expr'), semicolon
    assert eval_code("1+1;", ns) is None
    assert eval_code("1+1#;", ns) == 2
    assert eval_code("5-2  # comment with trailing semicolon ;", ns) == 3
    assert eval_code("4//2\n", ns) == 2
    assert eval_code("2**1\n\n", ns) == 2
    assert eval_code("4//2;\n", ns) is None
    assert eval_code("2**1;\n\n", ns) is None

    # 'last_expr_or_assign' mode, semicolon
    assert eval_code("1 + 1", ns, mode="last_expr_or_assign") == 2
    assert eval_code("x = 1 + 1", ns, mode="last_expr_or_assign") == 2
    assert eval_code("a = 5 ; a += 1", ns, mode="last_expr_or_assign") == 6
    assert eval_code("a = 5 ; a += 1;", ns, mode="last_expr_or_assign") is None
    assert eval_code("l = [1, 1, 2] ; l[0] = 0", ns, mode="last_expr_or_assign") is None

    # 'none' mode, (useless) semicolon
    assert eval_code("1 + 1", ns, mode="none") is None
    assert eval_code("x = 1 + 1", ns, mode="none") is None
    assert eval_code("a = 5 ; a += 1", ns, mode="none") is None
    assert eval_code("a = 5 ; a += 1;", ns, mode="none") is None
    assert eval_code("l = [1, 1, 2] ; l[0] = 0", ns, mode="none") is None


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
