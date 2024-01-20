from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["memory_allocator"])
def test_mytestname(selenium):
  import memory_allocator
