from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["lmdb"])
def test_lmdb(selenium):
    from tempfile import TemporaryDirectory

    import lmdb

    with TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/mytestdb"

        # create a new lmdb Environment
        env = lmdb.open(path, max_dbs=10)

        # make sure the environment is open
        assert env.open_db(b"mydb")

        # try to create a new lmdb Transaction
        with env.begin(write=True) as txn:
            # add a key-value pair to the Transaction
            txn.put(b"key", b"value")

        # try to retrieve the value we just added
        with env.begin() as txn:
            value = txn.get(b"key")
        assert value == b"value"

        # cleanup
        env.close()
