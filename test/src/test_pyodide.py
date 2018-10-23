import sys
from pathlib import Path
from textwrap import dedent

import pytest

sys.path.append(str(Path(__file__).parents[2] / 'src'))

from pyodide import find_imports  # noqa: E402


def test_find_imports():

    res = find_imports(dedent("""
           import six
           import numpy as np
           from scipy import sparse
           import matplotlib.pyplot as plt
           """))
    assert set(res) == {'numpy', 'scipy', 'six', 'matplotlib'}


def test_register_import_hook_mock_selenium(selenium_standalone):
    selenium = selenium_standalone
    from selenium.common.exceptions import JavascriptException

    with pytest.raises(JavascriptException) as err:
        selenium.run("""
             import not_existing
             """)
        assert ("ModuleNotFoundError: No module "
                "named 'not_existing'") in str(err)

    selenium.clean_logs()

    selenium.run("""
        import pyodide
        import sys

        pyodide.register_import_hook(mock_modules=['not_existing2'])

        import not_existing2
        not_existing2.some_method
        """)
    assert ('ImportWarning: Failed to import not_existing2,'
            ' mocking') in selenium.logs


def test_register_import_hook_mock():

    import pyodide

    n_meta_hooks_init = len(sys.meta_path)

    pyodide.register_import_hook(mock_modules=None, rename_modules=None)

    assert len(sys.meta_path) == n_meta_hooks_init

    with pytest.raises(ImportError):
        import not_existing  # noqa: F401

    # initialize the import hook
    pyodide.register_import_hook(mock_modules=['not_existing_a',
                                               'not_existing_b'])

    assert len(sys.meta_path) == n_meta_hooks_init + 1

    with pytest.warns(ImportWarning):
        import not_existing_a

    assert 'not_existing_a' in sys.modules

    method_a = not_existing_a.method_a

    assert hasattr(method_a, '__call__')

    with pytest.raises(NotImplementedError):
        method_a()

    with pytest.warns(ImportWarning):
        from not_existing_b import method_b

    with pytest.raises(NotImplementedError):
        method_b()

    # not whitelisted modules still raise ImportError
    with pytest.raises(ImportError):
        import not_existing_d  # noqa: F401

    # TODO: support the following
    # import not_existing_c.some_submodule

    # reset hook
    pyodide.register_import_hook()
    assert len(sys.meta_path) == n_meta_hooks_init
