import base64
import pathlib

from pyodide_test_runner import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "demo"
DATA_TRAIN = base64.b64encode((DEMO_PATH / "dermatology.data").read_bytes())


@run_in_pyodide(packages=["xgboost"], driver_timeout=60)
def test_compat():
    import numpy as np
    from xgboost.compat import lazy_isinstance

    a = np.array([1, 2, 3])
    assert lazy_isinstance(a, "numpy", "ndarray")
    assert not lazy_isinstance(a, "numpy", "dataframe")


def test_basic_classification(selenium):
    selenium.load_package("xgboost")
    selenium.set_script_timeout(60)
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
