from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_nodes(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.nodes"])


@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_geom(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.geom"])


@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_linalg(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.linalg"])


@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_sparse(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.tests.test_sparse"])


@run_in_pyodide(packages=["sisl-tests", "pytest"])
def test_physics_sparse(selenium):
    import pytest

    pytest.main(["--pyargs", "sisl.physics.tests.test_physics_sparse"])
