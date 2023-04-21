def test_bokeh(selenium):
    selenium.load_package("bokeh")
    selenium.run(
        """
        from bokeh.plotting import figure
        fig = figure()
        fig.line(range(3), [1, 4, 6])
        fig
        """
    )