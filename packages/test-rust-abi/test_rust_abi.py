import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail(reason="TODO: Fix me")
@run_in_pyodide(packages=["test-rust-abi"])
def test_rust_abi(selenium):
    from pathlib import Path

    from rust_abi_test import get_file_length

    contents = "this is the contents of the file\n" * 4
    Path("/test.txt").write_text(contents)
    assert get_file_length("/test.txt") == len(contents)
