# xgboost tests are copied from: https://github.com/dmlc/xgboost/tree/master/tests/python
import base64
import pathlib

import pytest
from pyodide_test_runner import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
DATA_TRAIN = base64.b64encode((DEMO_PATH / "dermatology.data").read_bytes())


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost"])
def test_compat(selenium):
    import numpy as np
    from xgboost.compat import lazy_isinstance

    a = np.array([1, 2, 3])
    assert lazy_isinstance(a, "numpy", "ndarray")
    assert not lazy_isinstance(a, "numpy", "dataframe")


@pytest.mark.driver_timeout(60)
def test_basic_classification(selenium):
    selenium.load_package("xgboost")
    selenium.run(
        f"""
        import base64
        with open("dermatology.data", "wb") as f:
            f.write(base64.b64decode({DATA_TRAIN!r}))

        import numpy as np
        import xgboost as xgb

        # label need to be 0 to num_class -1
        data = np.loadtxt('./dermatology.data', delimiter=',',
                converters={{33: lambda x:int(x == '?'), 34: lambda x:int(x) - 1}})
        sz = data.shape

        train = data[:int(sz[0] * 0.7), :]
        test = data[int(sz[0] * 0.7):, :]

        train_X = train[:, :33]
        train_Y = train[:, 34]

        test_X = test[:, :33]
        test_Y = test[:, 34]

        xg_train = xgb.DMatrix(train_X, label=train_Y)
        xg_test = xgb.DMatrix(test_X, label=test_Y)
        # setup parameters for xgboost
        param = {{}}
        # use softmax multi-class classification
        param['objective'] = 'multi:softmax'
        # scale weight of positive examples
        param['eta'] = 0.1
        param['max_depth'] = 6
        param['nthread'] = 4
        param['num_class'] = 6

        watchlist = [(xg_train, 'train'), (xg_test, 'test')]
        num_round = 5
        bst = xgb.train(param, xg_train, num_round, watchlist)
        # get prediction
        pred = bst.predict(xg_test)
        error_rate = np.sum(pred != test_Y) / test_Y.shape[0]
        assert error_rate < 0.1

        # do the same thing again, but output probabilities
        param['objective'] = 'multi:softprob'
        bst = xgb.train(param, xg_train, num_round, watchlist)
        # Note: this convention has been changed since xgboost-unity
        # get prediction, this is in 1D array, need reshape to (ndata, nclass)
        pred_prob = bst.predict(xg_test).reshape(test_Y.shape[0], 6)
        pred_label = np.argmax(pred_prob, axis=1)
        error_rate = np.sum(pred_label != test_Y) / test_Y.shape[0]
        assert error_rate < 0.1
        """
    )


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas", "pytest"])
def test_pandas(selenium):
    import numpy as np
    import pandas as pd
    import pytest
    import xgboost as xgb

    df = pd.DataFrame([[1, 2.0, True], [2, 3.0, False]], columns=["a", "b", "c"])
    dm = xgb.DMatrix(df, label=pd.Series([1, 2]))
    assert dm.feature_names == ["a", "b", "c"]
    assert dm.feature_types == ["int", "float", "i"]
    assert dm.num_row() == 2
    assert dm.num_col() == 3
    np.testing.assert_array_equal(dm.get_label(), np.array([1, 2]))

    # overwrite feature_names and feature_types
    dm = xgb.DMatrix(
        df,
        label=pd.Series([1, 2]),
        feature_names=["x", "y", "z"],
        feature_types=["q", "q", "q"],
    )
    assert dm.feature_names == ["x", "y", "z"]
    assert dm.feature_types == ["q", "q", "q"]
    assert dm.num_row() == 2
    assert dm.num_col() == 3

    # incorrect dtypes
    df = pd.DataFrame([[1, 2.0, "x"], [2, 3.0, "y"]], columns=["a", "b", "c"])
    with pytest.raises(ValueError):
        xgb.DMatrix(df)

    # numeric columns
    df = pd.DataFrame([[1, 2.0, True], [2, 3.0, False]])
    dm = xgb.DMatrix(df, label=pd.Series([1, 2]))
    assert dm.feature_names == ["0", "1", "2"]
    assert dm.feature_types == ["int", "float", "i"]
    assert dm.num_row() == 2
    assert dm.num_col() == 3
    np.testing.assert_array_equal(dm.get_label(), np.array([1, 2]))

    df = pd.DataFrame([[1, 2.0, 1], [2, 3.0, 1]], columns=[4, 5, 6])
    dm = xgb.DMatrix(df, label=pd.Series([1, 2]))
    assert dm.feature_names == ["4", "5", "6"]
    assert dm.feature_types == ["int", "float", "int"]
    assert dm.num_row() == 2
    assert dm.num_col() == 3

    df = pd.DataFrame({"A": ["X", "Y", "Z"], "B": [1, 2, 3]})
    dummies = pd.get_dummies(df)
    #    B  A_X  A_Y  A_Z
    # 0  1    1    0    0
    # 1  2    0    1    0
    # 2  3    0    0    1
    result, _, _ = xgb.data._transform_pandas_df(dummies, enable_categorical=False)
    exp = np.array([[1.0, 1.0, 0.0, 0.0], [2.0, 0.0, 1.0, 0.0], [3.0, 0.0, 0.0, 1.0]])
    np.testing.assert_array_equal(result, exp)
    dm = xgb.DMatrix(dummies)
    assert dm.feature_names == ["B", "A_X", "A_Y", "A_Z"]
    assert dm.feature_types == ["int", "int", "int", "int"]
    assert dm.num_row() == 3
    assert dm.num_col() == 4

    df = pd.DataFrame({"A=1": [1, 2, 3], "A=2": [4, 5, 6]})
    dm = xgb.DMatrix(df)
    assert dm.feature_names == ["A=1", "A=2"]
    assert dm.feature_types == ["int", "int"]
    assert dm.num_row() == 3
    assert dm.num_col() == 2

    df_int = pd.DataFrame([[1, 1.1], [2, 2.2]], columns=[9, 10])
    dm_int = xgb.DMatrix(df_int)
    df_range = pd.DataFrame([[1, 1.1], [2, 2.2]], columns=range(9, 11, 1))
    dm_range = xgb.DMatrix(df_range)
    assert dm_int.feature_names == ["9", "10"]  # assert not "9 "
    assert dm_int.feature_names == dm_range.feature_names

    # test MultiIndex as columns
    df = pd.DataFrame(
        [(1, 2, 3, 4, 5, 6), (6, 5, 4, 3, 2, 1)],
        columns=pd.MultiIndex.from_tuples(
            (
                ("a", 1),
                ("a", 2),
                ("a", 3),
                ("b", 1),
                ("b", 2),
                ("b", 3),
            )
        ),
    )
    dm = xgb.DMatrix(df)
    assert dm.feature_names == ["a 1", "a 2", "a 3", "b 1", "b 2", "b 3"]
    assert dm.feature_types == ["int", "int", "int", "int", "int", "int"]
    assert dm.num_row() == 2
    assert dm.num_col() == 6

    # test Index as columns
    df = pd.DataFrame([[1, 1.1], [2, 2.2]], columns=pd.Index([1, 2]))
    # print(df.columns, isinstance(df.columns, pd.Index))
    Xy = xgb.DMatrix(df)
    np.testing.assert_equal(np.array(Xy.feature_names), np.array(["1", "2"]))


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas"])
def test_pandas_slice(selenium):
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    rng = np.random.RandomState(1994)
    rows = 100
    X = rng.randint(3, 7, size=rows)
    X = pd.DataFrame({"f0": X})
    y = rng.randn(rows)
    ridxs = [1, 2, 3, 4, 5, 6]
    m = xgb.DMatrix(X, y)
    sliced = m.slice(ridxs)

    assert m.feature_types == sliced.feature_types


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas", "pytest"])
def test_pandas_categorical(selenium):
    import numpy as np
    import pandas as pd
    import pytest
    import xgboost as xgb

    rng = np.random.RandomState(1994)
    rows = 100
    X = rng.randint(3, 7, size=rows)
    X = pd.Series(X, dtype="category")
    X = pd.DataFrame({"f0": X})
    y = rng.randn(rows)
    m = xgb.DMatrix(X, y, enable_categorical=True)
    assert m.feature_types[0] == "c"

    X_0 = ["f", "o", "o"]
    X_1 = [4, 3, 2]
    X = pd.DataFrame({"feat_0": X_0, "feat_1": X_1})
    X["feat_0"] = X["feat_0"].astype("category")  # type: ignore[call-overload]
    transformed, _, feature_types = xgb.data._transform_pandas_df(
        X, enable_categorical=True
    )

    assert transformed[:, 0].min() == 0

    # test missing value
    X = pd.DataFrame({"f0": ["a", "b", np.NaN]})
    X["f0"] = X["f0"].astype("category")  # type: ignore[call-overload]
    arr, _, _ = xgb.data._transform_pandas_df(X, enable_categorical=True)
    assert not np.any(arr == -1.0)

    X = X["f0"]  # type: ignore[call-overload]
    y = y[: X.shape[0]]
    with pytest.raises(ValueError, match=r".*enable_categorical.*"):
        xgb.DMatrix(X, y)

    Xy = xgb.DMatrix(X, y, enable_categorical=True)
    assert Xy.num_row() == 3
    assert Xy.num_col() == 1


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas"])
def test_pandas_sparse(selenium):
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    rows = 100
    X = pd.DataFrame(
        {
            "A": pd.arrays.SparseArray(np.random.randint(0, 10, size=rows)),
            "B": pd.arrays.SparseArray(np.random.randn(rows)),
            "C": pd.arrays.SparseArray(
                np.random.permutation([True, False] * (rows // 2))
            ),
        }
    )
    y = pd.Series(pd.arrays.SparseArray(np.random.randn(rows)))
    dtrain = xgb.DMatrix(X, y)
    booster = xgb.train({}, dtrain, num_boost_round=4)
    predt_sparse = booster.predict(xgb.DMatrix(X))
    predt_dense = booster.predict(xgb.DMatrix(X.sparse.to_dense()))
    np.testing.assert_allclose(predt_sparse, predt_dense)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas", "pytest"])
def test_pandas_label(selenium):
    import numpy as np
    import pandas as pd
    import pytest
    import xgboost as xgb

    # label must be a single column
    df = pd.DataFrame({"A": ["X", "Y", "Z"], "B": [1, 2, 3]})
    with pytest.raises(ValueError):
        xgb.data._transform_pandas_df(df, False, None, None, "label", "float")

    # label must be supported dtype
    df = pd.DataFrame({"A": np.array(["a", "b", "c"], dtype=object)})
    with pytest.raises(ValueError):
        xgb.data._transform_pandas_df(df, False, None, None, "label", "float")

    df = pd.DataFrame({"A": np.array([1, 2, 3], dtype=int)})
    result, _, _ = xgb.data._transform_pandas_df(
        df, False, None, None, "label", "float"
    )
    np.testing.assert_array_equal(result, np.array([[1.0], [2.0], [3.0]], dtype=float))
    dm = xgb.DMatrix(np.random.randn(3, 2), label=df)
    assert dm.num_row() == 3
    assert dm.num_col() == 2


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["xgboost", "pandas"])
def test_pandas_weight(selenium):
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    kRows = 32
    kCols = 8

    X = np.random.randn(kRows, kCols)
    y = np.random.randn(kRows)
    w = np.random.uniform(size=kRows).astype(np.float32)
    w_pd = pd.DataFrame(w)
    data = xgb.DMatrix(X, y, w_pd)

    assert data.num_row() == kRows
    assert data.num_col() == kCols

    np.testing.assert_array_equal(data.get_weight(), w)
