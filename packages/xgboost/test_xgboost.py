import base64
import pathlib

from pyodide_test_runner import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "demo"
DATA_TRAIN = base64.b64encode((DEMO_PATH / "agaricus.txt.train").read_bytes())
DATA_TEST = base64.b64encode((DEMO_PATH / "agaricus.txt.test").read_bytes())


@run_in_pyodide(packages=["xgboost"])
def test_compat():
    import numpy as np
    from xgboost.compat import lazy_isinstance

    a = np.array([1, 2, 3])
    assert lazy_isinstance(a, "numpy", "ndarray")
    assert not lazy_isinstance(a, "numpy", "dataframe")


def test_basic(selenium):
    selenium.load_package("xgboost")
    selenium.run(
        f"""
        import base64
        with open("agaricus.txt.train", "wb") as f:
            f.write(base64.b64decode({DATA_TRAIN!r}))
        with open("agaricus.txt.test", "wb") as f:
            f.write(base64.b64decode({DATA_TEST!r}))

        import tempfile
        import xgboost as xgb
        dtrain = xgb.DMatrix('agaricus.txt.train')
        dtest = xgb.DMatrix('agaricus.txt.test')
        """
    )
