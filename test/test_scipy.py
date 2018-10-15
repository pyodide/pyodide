from pathlib import Path
import subprocess
import sys
from textwrap import dedent

import pytest

sys.path.append(str(Path(__file__).parents[1]))

from pyodide_build.common import HOSTPYTHON   # noqa: E402


def test_scipy_import(selenium_standalone, request):
    from selenium.common.exceptions import JavascriptException
    selenium = selenium_standalone

    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))
    selenium.load_package("scipy")
    selenium.run("""
        import scipy
        """)

    # supported modules
    for module in ['constants', 'fftpack', 'odr', 'sparse']:
        selenium.run(f"import scipy.{module}")

    # not yet built modules
    for module in ['cluster',  # needs sparse
                   'spatial',  # needs sparse
                   'integrate',  # needs special
                   'interpolate',  # needs linalg
                   'linalg',
                   'misc',   # needs special
                   'signal',  # needs special
                   'ndimage',  # needs special
                   'stats',  # need special
                   'optimize',  # needs minpack2
                   'special']:
        print(module)
        with pytest.raises(JavascriptException) as err:
            selenium.run(f"import scipy.{module}")
        assert ('ModuleNotFoundError' in str(err.value)
                or 'ImportError' in str(err.value))

    print(selenium.logs)


def test_built_so(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("scipy")

    cmd = dedent(r"""
        import scipy as sp
        import os

        base_dir = os.path.dirname(sp.__file__)

        out = []
        for (dirpath, dirnames, filenames) in os.walk(base_dir):
            for path in filenames:
                if path.endswith('.so'):
                    rel_path = os.path.relpath(dirpath, base_dir)
                    out.append(os.path.join(rel_path, path))
        print("\n".join(out))
        out
        """)

    out = subprocess.check_output(
            [HOSTPYTHON / 'bin' / 'python3', '-c', cmd])
    modules_host = out.decode('utf-8').split('\n')

    def _get_modules_name(modules):
        return set([path.split('.')[0] for path in modules if path])

    modules_host = _get_modules_name(modules_host)

    modules_target = selenium.run(cmd)
    modules_target = _get_modules_name(modules_target)

    print(f'Included modules: {len(modules_target)}')
    print(f'    {modules_target} ')
    print(f'\nMissing modules: {len(modules_host.difference(modules_target))}')
    print(f'     {modules_host.difference(modules_target)}')
