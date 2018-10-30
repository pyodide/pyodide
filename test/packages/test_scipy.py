from textwrap import dedent

import pytest


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
    for module in ['cluster', 'constants', 'fftpack', 'odr', 'sparse',
                   'interpolate', 'integrate',
                   'linalg',
                   'misc', 'ndimage', 'spatial', 'special'
                   ]:
        selenium.run(f"import scipy.{module}")

    # not yet built modules
    for module in []:
        print(module)
        with pytest.raises(JavascriptException) as err:
            selenium.run(f"import scipy.{module}")
        assert ('ModuleNotFoundError' in str(err.value)
                or 'ImportError' in str(err.value))

    print(selenium.logs)


def test_scipy_linalg(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("scipy")
    cmd = dedent(r"""
        import numpy as np
        import scipy as sp
        import scipy.linalg
        from numpy.testing import assert_allclose

        N = 10
        X = np.random.RandomState(42).rand(N, N)

        X_inv = scipy.linalg.inv(X)

        res = X.dot(X_inv)

        assert_allclose(res, np.identity(N),
                        rtol=1e-07, atol=1e-9)
        """)

    selenium.run(cmd)

    print(selenium.logs)


@pytest.mark.skip
def test_built_so(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("numpy")
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

    def _get_modules_name(modules):
        return set([path.split('.')[0] for path in modules if path])

    modules_target = selenium.run(cmd)
    modules_target = _get_modules_name(modules_target)

    print(f'Included modules: {len(modules_target)}')
    print(f'    {modules_target} ')
