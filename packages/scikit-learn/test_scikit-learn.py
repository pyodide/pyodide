import pytest
from pyodide_test_runner.fixture import selenium_context_manager


@pytest.mark.driver_timeout(40)
def test_scikit_learn(selenium_module_scope):
    if selenium_module_scope.browser == "chrome":
        pytest.xfail("Times out in chrome")
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scikit-learn")
        assert (
            selenium.run(
                """
                import numpy as np
                import sklearn
                from sklearn.linear_model import LogisticRegression

                rng = np.random.RandomState(42)
                X = rng.rand(100, 20)
                y = rng.randint(5, size=100)

                estimator = LogisticRegression(solver='liblinear')
                estimator.fit(X, y)
                print(estimator.predict(X))
                estimator.score(X, y)
                """
            )
            > 0
        )


@pytest.mark.driver_timeout(40)
def test_logistic_regression(selenium_module_scope):
    if selenium_module_scope.browser == "chrome":
        pytest.xfail("Times out in chrome")
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scikit-learn")
        selenium.run(
            """
            from sklearn.datasets import load_iris
            from sklearn.linear_model import LogisticRegression
            X, y = load_iris(return_X_y=True)
            clf = LogisticRegression(random_state=0).fit(X, y)
            print(clf.predict(X[:2, :]))
            print(clf.predict_proba(X[:2, :]))
            print(clf.score(X, y))
            """
        )
