from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["z3solver"],
)
def test_z3_socrates(selenium):
    """test to see if z3 is alive"""

    import z3
    obj = z3.DeclareSort("Object")
    human = z3.Function("Human", obj, z3.BoolSort())
    mortal = z3.Function("Mortal", obj, z3.BoolSort())
    # a well known philosopher
    socrates = z3.Const("socrates", obj)
    # free variables used in forall must be declared Const in python
    x = z3.Const("x", obj)
    axioms = [z3.ForAll([x], z3.Implies(human(x), mortal(x))), human(socrates)]
    s = z3.Solver()
    s.add(axioms)
    print(s.check())
    # prints sat so axioms are coherent
    assert z3.sat == s.check()
    # classical refutation
    s.add(z3.Not(mortal(socrates)))
    is_sat = s.check()
    print(is_sat)
    assert is_sat == z3.unsat
    # prints unsat so socrates is Mortal
    print(is_sat)
