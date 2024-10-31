from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pytest"])
def do_test(selenium, contents):
    from contextlib import redirect_stdout
    from io import StringIO
    from pathlib import Path

    import pytest

    Path("test_pytest.py").write_text(contents)

    out = StringIO()
    with redirect_stdout(out):
        result = pytest.main(["test_pytest.py"])

        assert result == 1

        out.seek(0)
        output = out.read()
        assert "2 passed" in output, output
        assert "1 failed" in output, output
        assert "1 warning" in output, output
        assert "This is a warning" in output, output


def test_pytest(selenium):
    contents = """
def test_success():
    assert 1 == 1

def test_warning():
    import warnings
    warnings.warn("This is a warning")

def test_fail():
    assert 1 == 2
"""

    do_test(selenium, contents)
