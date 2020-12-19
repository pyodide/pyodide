import sys
from pathlib import Path
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[2] / "src"))

from pyodide import find_imports  # noqa: E402

from selenium.common.exceptions import WebDriverException
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


def test_javascript_error(selenium):
    msg = "JsException: Error: This is a js error"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            from js import Error
            err = Error.new("This is a js error")
            err2 = Error.new("This is another js error")
            raise err
            """
        )


def test_javascript_error_back_to_js(selenium):
    selenium.run_js(
        """
        window.err = new Error("This is a js error")
        """
    )
    assert (
        selenium.run(
            """
        from js import err
        py_err = err
        type(py_err).__name__
        """
        )
        == "JsException"
    )
    assert selenium.run_js(
        """
        return pyodide.globals["py_err"] === err
        """
    )
