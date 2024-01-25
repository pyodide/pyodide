from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["python-flint"])
def test_python_flint(selenium):
    from flint import fmpz, fmpz_poly
    assert fmpz(1000) == 1000
    # assert fmpz(1000).partitions_p() == 24061467864032622473692149727991  # timeout
    a = fmpz_poly([1,2,3]); b = fmpz_poly([2,3,4])
    # assert a.gcd(a * b) == a  # timeout
