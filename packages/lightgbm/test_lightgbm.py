import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.skip_pyproxy_check
@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["lightgbm", "numpy"])
def test_train_predict(selenium):
    import lightgbm as lgb
    import numpy as np

    # --- train ---#
    data = np.random.rand(500, 10)
    label = np.random.randint(2, size=data.shape[0])  # binary target
    # use min_data_in_bin=1 for lgb.Dataset() and min_data_in_leaf=1 for lgb.train(),
    # to ensure at least some splits are made
    train_data = lgb.Dataset(data, label=label, params={"min_data_in_bin": 1})
    param = {"num_leaves": 11, "objective": "binary", "metric": "auc", "min_data_in_leaf": 1}
    num_round = 10
    bst = lgb.train(param, train_data, num_boost_round=num_round)

    # --- predict ---#
    data = np.random.rand(7, 10)
    ypred = bst.predict(data)
    print(ypred)
    assert ypred.shape == (7,)

    # --- serialize model ---#
    model_json = bst.dump_model()
    assert model_json["objective"] == "binary sigmoid:1"

    model_str = bst.model_to_string()
    assert "objective=binary" in model_str

    # model should successfully survive serialization-deserialization roundtrip
    np.testing.assert_allclose(
        lgb.Booster(model_str=model_str).predict(data),
        ypred
    )
