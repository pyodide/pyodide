import base64
import io
from functools import reduce
from pathlib import Path

import pytest
from pytest_pyodide import run_in_pyodide

REFERENCE_DATA_PATH = Path(__file__).parent / "test_data"

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
@run_in_pyodide(packages=["Cartopy", "matplotlib", "pyodide-http"])
def test_matplotlib(selenium):
    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt
    import pyodide_http

    pyodide_http.patch_all()

    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.coastlines()

    fd = io.BytesIO()
    plt.savefig(fd, format="svg")

    assert fd.getvalue() == base64.b64decode((REFERENCE_DATA_PATH / "cartopy.svg.b64").read_bytes())
