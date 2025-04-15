from functools import reduce

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import package_is_built

DECORATORS = [
    pytest.mark.xfail_browsers(node="No supported matplotlib backends on node"),
    pytest.mark.skip_refcount_check,
    pytest.mark.skip_pyproxy_check,
    pytest.mark.driver_timeout(60),
]


def matplotlib_test_decorator(f):
    return reduce(lambda x, g: g(x), DECORATORS, f)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["Cartopy"])
def test_imports(selenium):
    import cartopy
    import cartopy.trace

    print(cartopy, cartopy.trace)


@matplotlib_test_decorator
def test_matplotlib(selenium):
    if not package_is_built("pyodide-http"):
        pytest.skip("pyodide-http is not built")

    @run_in_pyodide(packages=["Cartopy", "matplotlib", "pyodide-http"])
    def run(selenium):
        import io

        import cartopy.crs as ccrs
        import matplotlib.pyplot as plt
        import pyodide_http

        pyodide_http.patch_all()

        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.coastlines()

        fd = io.BytesIO()
        plt.savefig(fd, format="svg")

        content = fd.getvalue().decode("utf8")
        assert len(content) > 100000
        assert content.startswith("<?xml")

    run(selenium)
