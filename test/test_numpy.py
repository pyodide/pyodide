def test_numpy(selenium):
    selenium.load_package("numpy")
    selenium.run("import numpy")
    x = selenium.run("numpy.zeros((32, 64))")
    assert len(x) == 32
    assert all(len(y) == 64 for y in x)
    for y in x:
        assert all(z == 0 for z in y)
