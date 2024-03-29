from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "pydoc_data"], pytest_assert_rewrites=False)
def test_pydoc(selenium):
    from test.libregrtest.main import main

    name = "test_pydoc"

    ignore_tests = [
        "test_server",  # fork
        "test_synopsis_sourceless",  # expects __pycache__
        "test_mixed_case_module_names_are_lower_cased",  # incompatible with zipimport
        "test_importfile",  # incompatible with zipimport
    ]
    match_tests = [[pat, False] for pat in ignore_tests]
    try:
        main([name], match_tests=match_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
