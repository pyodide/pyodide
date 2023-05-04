from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["bokeh"])
def test_bokeh(selenium):
    """
    Check whether any errors occur when drawing a basic plot.
    Intended to function as a regression test.
    """
    from bokeh.plotting import figure

    fig = figure()
    fig.line(range(3), [1, 4, 6])
    del fig  # clean up the proxied variable
