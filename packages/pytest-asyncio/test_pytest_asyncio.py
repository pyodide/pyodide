from pytest_pyodide import run_in_pyodide

from conftest import requires_jspi


@run_in_pyodide(packages=["pytest-asyncio"])
def do_test(selenium, contents):
    from pathlib import Path

    Path("test_pytest_asyncio.py").write_text(contents)
    import pytest

    assert pytest.main(["test_pytest_asyncio.py"]) == 0


@requires_jspi
def test_pytest_asyncio(selenium):
    from pathlib import Path

    contents = (Path(__file__).parent / "inner_test_pytest_asyncio.py").read_text()
    do_test(selenium, contents)
