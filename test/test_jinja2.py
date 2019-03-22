def test_jinja2(selenium):
    selenium.load_package("Jinja2")
    selenium.run("""
        import jinja2

        template = jinja2.Template('Hello {{ name }}!')
    """)
    content = selenium.run("""template.render(name='Zach')""")
    assert content == 'Hello Zach!'
