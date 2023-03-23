from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["dlib"])
def test_pyyaml(selenium):
    import dlib

    version = dlib.__version__
    major, minor, sub = version.split(".")
    assert major == "19" and minor == "24"
