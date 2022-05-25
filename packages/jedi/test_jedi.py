from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(selenium_fixture_name="selenium_standalone", packages=["jedi"])
def test_jedi():
    import jedi

    script = jedi.Script("import json\njson.lo", path="example.py")
    completions = script.complete(2, len("json.lo"))
    assert [el.name for el in completions] == ["load", "loads"]
