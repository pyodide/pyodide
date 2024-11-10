from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["clingo"])
def test_clingo(selenium):
    from clingo.control import Control
    from clingo.symbol import Number

    class Context:
        def inc(self, x):
            return Number(x.number + 1)

        def seq(self, x, y):
            return [x, y]

    def on_model(m):
        print(m)

    ctl = Control()
    ctl.add(
        "base",
        [],
        """
    p(@inc(10)).
    q(@seq(1,2)).
    """,
    )

    ctl.ground([("base", [])], context=Context())
    solution = ctl.solve(on_model=on_model)
    assert solution.satisfiable
