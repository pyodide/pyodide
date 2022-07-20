from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["z3solver"],
)
def test_z3_socrates(selenium):
    """ test to see if z3 is alive """
    import z3
    sObject = z3.DeclareSort('Object')
    fHuman = z3.Function('Human', sObject, z3.BoolSort())
    fMortal = z3.Function('Mortal', sObject, z3.BoolSort())
    # a well known philosopher
    socrates = z3.Const('socrates', sObject)
    # free variables used in forall must be declared Const in python
    x = z3.Const('x', sObject)
    axioms = [z3.ForAll([x], z3.Implies(fHuman(x), fMortal(x))), fHuman(socrates)]
    s = z3.Solver()
    s.add(axioms)
    print(s.check()) # prints sat so axioms are coherent
    assert(z3.sat == s.check())
    # classical refutation
    s.add(z3.Not(fMortal(socrates)))
    is_sat = s.check()
    print(is_sat)
    assert(is_sat == z3.unsat)
    print(is_sat) # prints unsat so socrates is Mortal

