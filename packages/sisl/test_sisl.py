import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_load_sisl(selenium):
    """Loading sisl takes a really long time so this separates it out to reduce
    the chance that test_nodes times out.
    """
    pass


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_nodes(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.nodes"])


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_geom(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.geom"])


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_linalg(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.linalg"])


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_sparse(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.tests.test_sparse"])


@pytest.mark.xfail_browsers(firefox="Too slow")
@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_physics_sparse(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.physics.tests.test_physics_sparse"])
