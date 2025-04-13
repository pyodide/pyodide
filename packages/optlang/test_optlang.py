import pytest


def test_optlang(selenium):
    selenium.load_package("optlang")
    selenium.run(
        """
        from optlang import Model, Variable, Constraint, Objective

        # All the (symbolic) variables are declared, with a name and optionally a lower and/or upper bound.
        x1 = Variable('x1', lb=0)
        x2 = Variable('x2', lb=0)
        x3 = Variable('x3', lb=0)

        # A constraint is constructed from an expression of variables and a lower and/or upper bound (lb and ub).
        c1 = Constraint(x1 + x2 + x3, ub=100)
        c2 = Constraint(10 * x1 + 4 * x2 + 5 * x3, ub=600)
        c3 = Constraint(2 * x1 + 2 * x2 + 6 * x3, ub=300)

        # An objective can be formulated
        obj = Objective(10 * x1 + 6 * x2 + 4 * x3, direction='max')

        # Variables, constraints and objective are combined in a Model object, which can subsequently be optimized.
        model = Model(name='Simple model')
        model.objective = obj
        model.add([c1, c2, c3])

        status = model.optimize()
        """
    )
    result = selenium.run("model.status")
    assert result == "optimal"
    result = selenium.run("model.objective.value")
    assert result == pytest.approx(733.3333, abs=1e-4)
    result = selenium.run("model.variables['x1'].primal")
    assert result == pytest.approx(33.3333, abs=1e-4)
    result = selenium.run("model.variables['x2'].primal")
    assert result == pytest.approx(66.6667, abs=1e-4)
    result = selenium.run("model.variables['x3'].primal")
    assert result == pytest.approx(0.0000, abs=1e-4)
