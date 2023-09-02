from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["thinc", "numpy"])
def test_thinc(selenium):
    import numpy
    from thinc.api import Linear, zero_init

    n_in = numpy.zeros((128, 16), dtype="f")
    n_out = numpy.zeros((128, 10), dtype="f")

    model = Linear(nI=n_in.shape[1], nO=n_out.shape[1], init_W=zero_init)
    nI = model.get_dim("nI")
    nO = model.get_dim("nO")
    assert nI == 16
    assert nO == 10
