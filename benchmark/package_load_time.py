import pytest

from conftest import package_is_built


def refresh(selenium):
    selenium.clean_logs()
    selenium.refresh()
    selenium.load_pyodide()
    selenium.initialize_pyodide()
    selenium.save_state()
    selenium.restore_state()


def package_load_time(selenium, package_name):
    refresh(selenium)
    selenium.load_package(package_name)


@pytest.mark.benchmark(
    min_rounds=5,
)
@pytest.mark.parametrize(
    "package_name",
    ["micropip", "numpy", "matplotlib", "pandas", "scipy", "scikit-learn"],
)
def test_package_load_time(selenium, benchmark, package_name):
    if not package_is_built(package_name):
        pytest.xfail(f"Package {package_name} is not built")

    benchmark(package_load_time, selenium, package_name)
