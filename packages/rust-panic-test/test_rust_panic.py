from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["rust-panic-test"])
def test_rust_panic(selenium):
    from pytest import raises
    from rust_panic_test import PanicException, panic_test

    assert not panic_test(bytes([20]))
    assert panic_test(bytes([10]))
    with raises(PanicException):
        panic_test(bytes([1]))
