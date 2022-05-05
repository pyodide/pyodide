from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["bitarray-tests"])
def test_bitarray():
    import bitarray

    bitarray.test()
