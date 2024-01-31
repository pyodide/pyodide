from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["cypari2"])
def test_cypari2(selenium):
    import cypari2
    pari = cypari2.Pari()
    p = pari('x^2 + 1')
    assert p.polisirreducible()
