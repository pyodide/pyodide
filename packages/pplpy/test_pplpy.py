from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pplpy"])
def test_pplpy(selenium):
    from ppl import Constraint, Variable

    x = Variable(0)
    y = Variable(1)
    c = x + 3 * y == 1
    cc = Constraint(c)
    assert c.is_equivalent_to(cc)
