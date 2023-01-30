from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "pydecimal"], pytest_assert_rewrites=False)
def test_distutils(selenium):
    import sys
    import unittest
    import unittest.mock
    from test import libregrtest  # type:ignore[attr-defined]

    name = "test_pydecimal"

    ignore_tests = []
    try:
        libregrtest.main([name], ignore_tests=ignore_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
