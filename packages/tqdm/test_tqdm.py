from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tqdm"], pytest_assert_rewrites=False)
def test_tqdm(selenium):
    import time
    import warnings

    import tqdm

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("error")
        for _ in tqdm.tqdm(range(10), desc="Processing"):
            time.sleep(0.1)
    assert len(w) == 0
