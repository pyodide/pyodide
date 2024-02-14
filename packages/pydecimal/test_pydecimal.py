from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "pydecimal"], pytest_assert_rewrites=False)
def test_pydecimal(selenium):
    from test.libregrtest.main import main

    name = "test_decimal"

    ignore_tests = [
        "test_context_subclassing",  # floating point
        "test_none_args",  # Some context issue?
        "test_threading",
    ]
    match_tests = [[pat, False] for pat in ignore_tests]

    try:
        main([name], match_tests=match_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
