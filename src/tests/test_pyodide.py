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
    msg = "pyodide.JsException: Error: hi"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            from js import Error
            err = Error.new("This is a js error")
            raise err
            """
        )

def test_javascript_error_no_new(selenium):
    msg = "pyodide.JsException: Error: hi"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            from js import Error
            err = Error("This is a js error")
            raise err
            """
        )

def test_javascript_error_back_to_js(selenium):
    msg = "pyodide.JsException: Error: hi"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            from js import Error
            err = Error.new("This is a js error")
            """
        )
        selenium.run_js(
            """
            pyodide.globals["err"]
            """
        )