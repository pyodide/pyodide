import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["river"])
def test_linear_regression(selenium):
    from river import datasets, evaluate, linear_model, metrics, preprocessing

    dataset = datasets.TrumpApproval()

    model = preprocessing.StandardScaler() | linear_model.LinearRegression(
        intercept_lr=0.1
    )
    metric = metrics.MAE()

    evaluate.progressive_val_score(dataset, model, metric)
