import pytest
from pytest_pyodide import run_in_pyodide

COMPRESSIONS = ("SNAPPY", "GZIP", "LZ4", "BROTLI", "ZSTD")


# just check that we can read and write random data
@pytest.mark.parametrize("compression", COMPRESSIONS)
@run_in_pyodide(packages=["fastparquet", "packaging"])
def test_simple_table(selenium, compression):
    import fastparquet  # type: ignore
    import pandas as pd  # type: ignore
    import numpy as np  # type: ignore
    from tempfile import TemporaryDirectory
    from pathlib import Path

    df = pd.DataFrame(np.random.randn(131072, 4), columns=list("ABCD"))
    with TemporaryDirectory() as td:
        name = Path(td) / "test.parquet"
        fastparquet.write(name, df, compression=compression)
        df2 = fastparquet.ParquetFile(name).to_pandas()
        assert df2.equals(df)
