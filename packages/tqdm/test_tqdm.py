from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tqdm"], pytest_assert_rewrites=False)
def test_test(selenium):
    # this is tested in test_core_python.py instead
    pass
