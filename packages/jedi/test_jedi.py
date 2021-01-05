def test_jedi(selenium_standalone):
    selenium_standalone.load_package("jedi")
    result = selenium_standalone.run(
        """
        import jedi
        script = jedi.Script("import json\\njson.lo", path='example.py')
        completions = script.complete(2, len('json.lo'))
        [el.name for el in completions]
        """
    )
    assert result == ["load", "loads"]


def test_completions(selenium_standalone):
    selenium_standalone.load_package("jedi")
    result = selenium_standalone.run(
        """
        import pyodide
        pyodide.get_completions('import sys\\nsys.v')
        """
    )
    assert result == ["version", "version_info"]
