from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["argon2_cffi"])
def test_argon2_cffi(selenium):
    import argon2

    ph = argon2.PasswordHasher(parallelism=1)
    hash = ph.hash("test")

    assert ph.verify(hash, "test") is True
