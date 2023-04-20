from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["h5py"])
def test_h5py(selenium):
    import h5py

    with h5py.File("mytestfile.hdf5", "a") as f:
        dset = f.create_dataset("mydataset", (100,), dtype="i")
        grp = f.create_group("subgroup")
        dset2 = grp.create_dataset("another_dataset", (50,), dtype="f")

        assert f.name == "/"
        assert dset.name == "/mydataset"
        assert dset2.name == "/subgroup/another_dataset"

    f = h5py.File("mytestfile.hdf5", "r")
    assert sorted(list(f.keys())) == ["mydataset", "subgroup"]
