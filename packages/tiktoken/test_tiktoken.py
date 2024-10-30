from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["tiktoken"])
def test_tiktoken(selenium):
  import tiktoken
  encoding = tiktoken.get_encoding("cl100k_base")
  test_str = "Hello, world!"
  encoded = encoding.encode(test_str)
  decoded = encoding.decode(encoded)
  assert decoded == test_str