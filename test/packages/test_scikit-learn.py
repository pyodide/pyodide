import pytest


def test_scikit_learn(selenium_standalone, request):
    selenium = selenium_standalone
    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))
    selenium.load_package("scikit-learn")
    assert selenium.run("""
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
        """) > 0
