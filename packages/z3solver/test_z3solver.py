from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["z3solver"],
)
def test_z3_socrates(selenium):
    import io

    from z3 import *

    Object = DeclareSort('Object')
    Human = Function('Human', Object, BoolSort())
    Mortal = Function('Mortal', Object, BoolSort())

    # a well known philosopher
    socrates = Const('socrates', Object)

    # free variables used in forall must be declared Const in python
    x = Const('x', Object)

    axioms = [ForAll([x], Implies(Human(x), Mortal(x))), Human(socrates)]

    s = Solver()
    s.add(axioms)

    print(s.check()) # prints sat so axioms are coherent

    # classical refutation
    s.add(Not(Mortal(socrates)))

    print(s.check()) # prints unsat so socrates is Mortal


