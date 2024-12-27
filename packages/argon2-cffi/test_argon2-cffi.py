import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["argon2-cffi", "argon2-cffi-bindings"])
async def argon2_cffi_helper(selenium):
    import argon2

    ph = argon2.PasswordHasher(parallelism=1)
    hash = ph.hash("test")

    assert ph.verify(hash, "test") is True

    with pytest.raises(argon2.exceptions.Argon2Error):
        argon2.PasswordHasher(parallelism=2).hash("test")


def test_argon2(selenium):
    argon2_cffi_helper(selenium)
