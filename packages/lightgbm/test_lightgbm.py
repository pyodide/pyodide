import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["lightgbm", "numpy"])
def test_train_predict(selenium):
    import lightgbm as lgb
    import numpy as np

    data = np.random.rand(50, 10)  # 50 entities, each contains 10 features
    label = np.random.randint(2, size=50)  # binary target
    train_data = lgb.Dataset(data, label=label)
    param = {"num_leaves": 11, "objective": "binary", "metric": "auc"}
    num_round = 10
    bst = lgb.train(param, train_data, num_round)
    data = np.random.rand(7, 10)
    ypred = bst.predict(data)
    print(ypred)
    assert ypred.shape == (7,)
