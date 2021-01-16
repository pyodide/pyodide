from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["cloudpickle"])
def test_cloudpickle():
    import cloudpickle

    squared = lambda x: x ** 2
    pickled_lambda = cloudpickle.dumps(squared)

    import pickle

    new_squared = pickle.loads(pickled_lambda)
    assert new_squared(2) == 4

    CONSTANT = 42

    def my_function(data: int) -> int:
        return data + CONSTANT

    pickled_function = cloudpickle.dumps(my_function)
    depickled_function = pickle.loads(pickled_function)
    assert depickled_function(43) == 85
