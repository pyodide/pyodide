from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tree-sitter-python"])
def test_tree_sitter_python(selenium):
    import textwrap

    import tree_sitter_python
    from tree_sitter import Language, Parser

    PY_LANGUAGE = Language(tree_sitter_python.language())
    parser = Parser(PY_LANGUAGE)

    code = bytes(
        textwrap.dedent(
            """
        def foo():
            if bar:
                baz()
        """
        ),
        "utf-8",
    )
    tree = parser.parse(code)
    root_node = tree.root_node

    assert str(root_node) == (
        "(module "
        "(function_definition "
        "name: (identifier) "
        "parameters: (parameters) "
        "body: (block "
        "(if_statement "
        "condition: (identifier) "
        "consequence: (block "
        "(expression_statement (call "
        "function: (identifier) "
        "arguments: (argument_list))))))))"
    )
