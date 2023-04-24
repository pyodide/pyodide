from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["bokeh"])
def test_xyzservices(selenium):
    """
    Check whether any errors occur by testing basic functionality.
    Intended to function as a regression test.
    Might fail if xyzservices is upgraded and the data
    or API changes.
    """
    selenium.load_package("xyzservices")
    selenium.run(
        """
        import xyzservices.providers
        # assert the module produces something for this
        assert xyzservices.providers.CartoDB.Positron.url
        """
    )
