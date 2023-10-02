from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["river"])
def test_linear_regression(selenium):
    from river import datasets
    from river import evaluate
    from river import linear_model
    from river import metrics
    from river import preprocessing

    dataset = datasets.TrumpApproval()

    model = (
        preprocessing.StandardScaler() |
        linear_model.LinearRegression(intercept_lr=.1)
    )
    metric = metrics.MAE()

    evaluate.progressive_val_score(dataset, model, metric)
