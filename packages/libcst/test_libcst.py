from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["libcst"])
def test_libcst(selenium):
    import libcst

    libcst.parse_module("def f[T](foo): ...")
