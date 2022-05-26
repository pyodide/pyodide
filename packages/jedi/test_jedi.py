from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["jedi"])
def test_jedi(selenium_standalone):
    import jedi

    script = jedi.Script("import json\njson.lo", path="example.py")
    completions = script.complete(2, len("json.lo"))
    assert [el.name for el in completions] == ["load", "loads"]
