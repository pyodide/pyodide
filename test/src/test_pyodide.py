import sys
from pathlib import Path
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[2] / 'src'))

from pyodide import find_imports  # noqa: E402


def test_find_imports():

    res = find_imports(dedent("""
           import six
           import numpy as np
           from scipy import sparse
           """))
    assert set(res) == {'numpy', 'scipy', 'six'}
