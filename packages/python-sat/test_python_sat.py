import pytest
from pytest_pyodide import run_in_pyodide

solvers = [
    "cadical",
    "gluecard30",
    "gluecard41",
    "glucose30",
    "glucose41",
    "maplechrono",
    "maplecm",
    "maplesat",
    "mergesat3",
    "minicard",
    "minisat22",
    "minisat-gh",
]


@pytest.mark.parametrize("name", solvers)
@run_in_pyodide(packages=["python-sat"])
def test_solvers(selenium, name):
    from pysat.formula import CNF
    from pysat.solvers import Solver

    cnf = CNF(from_clauses=[[1, 2, 3], [-1, 2], [-2]])

    with Solver(name=name, bootstrap_with=cnf) as solver:
        solver.solve()
        stats = solver.accum_stats()
        assert "conflicts" in stats, f"No conflicts for {name}"
        assert "decisions" in stats, f"No decisions for {name}"
        assert "propagations" in stats, f"No propagations for {name}"
        assert "restarts" in stats, f"No restarts for {name}"


@run_in_pyodide(packages=["python-sat"])
def test_atmost(selenium):
    from pysat.card import CardEnc
    from pysat.formula import IDPool

    vp = IDPool()
    n = 20
    b = 50
    assert n <= b

    literals = [vp.id(v) for v in range(1, n + 1)]
    top = vp.top

    G = CardEnc.atmost(literals, b, vpool=vp)

    assert len(G.clauses) == 0

    try:
        assert vp.top >= top
    except AssertionError:
        print(f"\nvp.top = {vp.top} (expected >= {top})\n")
        raise


@run_in_pyodide(packages=["python-sat"])
def test_atmost1(selenium):
    from pysat.card import CardEnc, EncType
    from pysat.solvers import MinisatGH

    encs = list(
        filter(
            lambda name: not name.startswith("__") and name != "native", dir(EncType)
        )
    )
    for l in range(10, 20):
        for e in encs:
            cnf = CardEnc.atmost(
                lits=list(range(1, l + 1)), bound=1, encoding=getattr(EncType, e)
            )

            # enumerating all models
            with MinisatGH(bootstrap_with=cnf) as solver:
                for _num, model in enumerate(solver.enum_models(), 1):
                    solver.add_clause([-l for l in model[:l]])

            assert _num == l + 1, f"wrong number of models for AtMost-1-of-{l} ({e})"
