from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["Jinja2"])
def test_jinja2():
    import jinja2

    template = jinja2.Template("Hello {{ name }}!")
    content = template.render(name="Zach")
    assert content == "Hello Zach!"
