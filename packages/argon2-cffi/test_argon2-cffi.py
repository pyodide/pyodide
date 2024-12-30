import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["argon2-cffi"])
def argon2_cffi_helper(selenium):
    import argon2

    ph = argon2.PasswordHasher(parallelism=1)
    hash = ph.hash("test")

    assert ph.verify(hash, "test") is True

    with pytest.raises(argon2.exceptions.UnsupportedParamsError) as exinfo:
        argon2.PasswordHasher(parallelism=2).hash("test")

    assert (
        str(exinfo.value)
        == "within wasm/wasi environments `parallelism` must be set to 1"
    )

    # test default params
    ph = argon2.PasswordHasher()
    hash = ph.hash("test")

    assert ph.verify(hash, "test") is True


def test_argon2(selenium):
    argon2_cffi_helper(selenium)
