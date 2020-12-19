def assert_js_to_py_to_js(selenium, name):
    selenium.run_js(f"window.obj = {name};")
    selenium.run("from js import obj")
    assert selenium.run_js("return pyodide.globals['obj'] === obj")


def assert_js_to_py_to_js_literal(selenium, lit):
    selenium.run_js(f"window.literal = {lit};")
    assert_js_to_py_to_js(selenium, "literal")


def assert_py_to_js_to_py(selenium, name):
    selenium.run_js(f"window.obj = pyodide.globals['{name}'];")
    assert selenium.run(
        f"""
        from js import obj
        print(obj, {name})
        obj == {name}
        """
    )


def assert_py_to_js_to_py_identity(selenium, name):
    selenium.run_js(f"window.obj = pyodide.globals['{name}'];")
    assert selenium.run(
        f"""
        from js import obj
        obj is {name}
        """
    )


def assert_py_to_js_to_py_literal(selenium, lit):
    print("py_to_js_to_py", lit)
    selenium.run(f"literal = {lit}")
    assert_py_to_js_to_py(selenium, "literal")


def test_literal_conversions(selenium):
    for s in ["undefined", "true", "false"]:
        assert_js_to_py_to_js_literal(selenium, s)
    for s in ["None", "True", "False"]:
        assert_py_to_js_to_py_literal(selenium, s)

    for s in ["1", "1.077323", '"1"', '"1ȫ"', '"֍"', '"abᦗ"', '"⨶"']:
        assert_js_to_py_to_js_literal(selenium, s)
        assert_py_to_js_to_py_literal(selenium, s)


def test_list_from_py(selenium):
    selenium.run("x = [1,2,3]")
    assert_py_to_js_to_py_identity(selenium, "x")


def test_list_from_js(selenium):
    selenium.run_js("window.x = [1,2,3];")
    assert_js_to_py_to_js(selenium, "x")


def test_dict_from_py(selenium):
    selenium.run("x = { 'a' : 1, 'b' : 2, 0 : 3 }")
    assert_py_to_js_to_py_identity(selenium, "x")


def test_dict_from_js(selenium):
    selenium.run_js("window.x = { a : 1, b : 2, 0 : 3 };")
    assert_js_to_py_to_js(selenium, "x")


def test_error_from_js(selenium):
    selenium.run_js("window.err = new Error('hello there?');")
    assert_js_to_py_to_js(selenium, "err")


def test_error_from_python(selenium):
    selenium.run("err = Exception('hello there?');")
    assert_py_to_js_to_py(selenium, "err")
