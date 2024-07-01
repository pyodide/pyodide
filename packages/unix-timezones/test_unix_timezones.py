from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["unix-timezones"])
def test_install_unix_timezones(selenium):
    from pathlib import Path

    assert Path("/usr/share/zoneinfo/UTC").exists()
