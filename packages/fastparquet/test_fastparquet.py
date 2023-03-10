import pytest
from pytest_pyodide import run_in_pyodide

COMPRESSIONS = ("SNAPPY", "GZIP", "LZ4", "BROTLI", "ZSTD")


# just check that we can read and write random data
@pytest.mark.driver_timeout(60)
@pytest.mark.parametrize("compression", COMPRESSIONS)
@run_in_pyodide(packages=["fastparquet"])
def test_simple_table(selenium, compression):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import fastparquet
    import numpy as np
    import pandas as pd

    df = pd.DataFrame(np.random.randn(131072, 4), columns=list("ABCD"))
    with TemporaryDirectory() as td:
        name = Path(td) / "test.parquet"
        fastparquet.write(name, df, compression=compression)
        df2 = fastparquet.ParquetFile(name).to_pandas()
        assert df2.equals(df)
