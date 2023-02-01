from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "pydoc_data"], pytest_assert_rewrites=False)
def test_pydoc(selenium):
    from test import libregrtest  # type:ignore[attr-defined]

    name = "test_pydoc"

    ignore_tests = [
        "test_server",  # fork
        "test_synopsis_sourceless",  # expects __pycache__
    ]
    try:
        libregrtest.main([name], ignore_tests=ignore_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
