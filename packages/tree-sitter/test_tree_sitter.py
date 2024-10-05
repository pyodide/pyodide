from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tree-sitter"])
def test_tree_sitter(selenium):
    import tree_sitter

    assert hasattr(tree_sitter, "Language")
    assert hasattr(tree_sitter, "Node")
