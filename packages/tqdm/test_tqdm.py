from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tqdm"], pytest_assert_rewrites=False)
def test_tqdm(selenium):
    import warnings

    with warnings.catch_warnings(record=True) as w:
        for i in tqdm(range(100), desc="Processing"):
            time.sleep(0.1)
        assert len(w) == 0
