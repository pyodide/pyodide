from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["css_inline"])
def test_inline_html(selenium):
    import css_inline

    html = """<html>
  <head>
    <style>h1 { color:blue; }</style>
  </head>
  <body>
    <h1>Big Text</h1>
  </body>
</html>"""

    assert '<h1 style="color: blue;">Big Text</h1>' in css_inline.inline(html)
