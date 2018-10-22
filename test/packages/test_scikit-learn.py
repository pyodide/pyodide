from textwrap import dedent

def test_scikit_learn(selenium_standalone):
    selenium = selenium_standalone
    # no automatic depedency resolution for now
    selenium.load_package(["numpy", "joblib"])
    selenium.load_package("scipy")
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
    print(selenium.logs)

def test_import(selenium_standalone):
    selenium = selenium_standalone
    # no automatic depedency resolution for now
    selenium.load_package(["numpy", "joblib"])
    selenium.load_package("scipy")
    selenium.load_package("scikit-learn")
    cmd = dedent("""
            import sklearn
            import sklearn.calibration
            import sklearn.calibration
            import sklearn.cluster
            import sklearn.compose
            import sklearn.covariance
            import sklearn.cross_decomposition
            import sklearn.datasets
            import sklearn.decomposition
            import sklearn.discriminant_analysis
            import sklearn.dummy
            import sklearn.ensemble
            import sklearn.exceptions
            import sklearn.externals
            import sklearn.feature_extraction
            import sklearn.feature_selection
            import sklearn.gaussian_process
            import sklearn.impute
            import sklearn.isotonic
            import sklearn.kernel_approximation
            import sklearn.kernel_ridge
            import sklearn.linear_model
            import sklearn.manifold
            import sklearn.metrics
            import sklearn.mixture
            import sklearn.model_selection
            import sklearn.multiclass
            import sklearn.multioutput
            import sklearn.naive_bayes
            import sklearn.neighbors
            import sklearn.neural_network
            import sklearn.pipeline
            import sklearn.preprocessing
            import sklearn.random_projection
            import sklearn.semi_supervised
            import sklearn.svm
            import sklearn.tree
            import sklearn.utils
            """).splitlines()

    for line in cmd:
        try:
            selenium.run(line)
            print(f'{line} -- OK')
        except:
            print(f'Error: {line} failed')
            print(selenium.logs)
