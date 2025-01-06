from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["polars"])
def test_polars_basics(selenium):
    import polars as pl

    df = pl.DataFrame(
        {"a": [1, 2, 3, 4], "b": [10, 20, 30, 40], "c": ["x", "y", "z", "w"]}
    )

    assert df.shape == (4, 3)
    assert df.select("a").to_series().to_list() == [1, 2, 3, 4]

    result = df.select(pl.col("b").sum()).item()
    assert result == 100

    result = df.select(pl.col("c").str.to_uppercase()).to_series().to_list()
    assert result == ["X", "Y", "Z", "W"]


@run_in_pyodide(packages=["polars"])
def test_polars_operations(selenium):
    import polars as pl

    df = pl.DataFrame({"nums": [1, 2, 3, None, 5], "groups": ["A", "A", "B", "B", "C"]})

    assert df["nums"].null_count() == 1

    result = (
        df.group_by("groups")
        .agg(pl.col("nums").mean())
        .sort("groups")
        .to_dict(as_series=False)
    )

    expected = {"groups": ["A", "B", "C"], "nums": [1.5, 3.0, 5.0]}
    assert result == expected


@run_in_pyodide(packages=["polars"])
def test_polars_dtypes(selenium):
    import polars as pl

    df = pl.DataFrame(
        {
            "ints": [1, 2, 3],
            "floats": [1.1, 2.2, 3.3],
            "strings": ["a", "b", "c"],
            "bools": [True, False, True],
        }
    )

    assert df["ints"].dtype == pl.Int64
    assert df["floats"].dtype == pl.Float64
    assert df["strings"].dtype == pl.String
    assert df["bools"].dtype == pl.Boolean

    result = df.select(pl.col("ints").cast(pl.Float32))
    assert result["ints"].dtype == pl.Float32
