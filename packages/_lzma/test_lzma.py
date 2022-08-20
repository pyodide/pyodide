from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "_lzma"], pytest_assert_rewrites=False)
def test_lzma(selenium):
    # TODO: libregrtest.main(["test_lzma"]) doesn't collect any tests for some unknown reason.

    import test.test_lzma
    import unittest

    suite = unittest.TestSuite(
        [unittest.TestLoader().loadTestsFromModule(test.test_lzma)]
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    assert result.wasSuccessful()
