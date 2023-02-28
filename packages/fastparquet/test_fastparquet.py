import pytest
from pytest_pyodide import run_in_pyodide

COMPRESSIONS = ("SNAPPY", "GZIP", "LZ4", "BROTLI", "ZSTD")

# just check that we can read and write random data
@pytest.mark.parametrize("compression", COMPRESSIONS)
@run_in_pyodide(packages=["fastparquet"])
def test_simple_table(selenium, compression):
    from tempfile import NamedTemporaryFile

    import fastparquet # type: ignore
    import numpy as np
    import pandas as pd # type: ignore

    df = pd.DataFrame(np.random.randn(131072, 8), columns=list("ABCDEFGH"))
    with NamedTemporaryFile(suffix=".parquet") as tf:
        fastparquet.write(tf, df, compression=compression)
        df2 = fastparquet.read(tf)
        assert df2 == df
