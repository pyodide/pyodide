from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["Jinja2"])
def test_jinja2(selenium):
    import jinja2

    template = jinja2.Template("Hello {{ name }}!")
    content = template.render(name="Zach")
    assert content == "Hello Zach!"
