from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tree-sitter-go"])
def test_tree_sitter_go(selenium):
    import textwrap

    import tree_sitter_go
    from tree_sitter import Language, Parser

    GO_LANGUAGE = Language(tree_sitter_go.language())
    parser = Parser(GO_LANGUAGE)

    code = bytes(
        textwrap.dedent(
            """
        func foo() {
            if bar {
                baz()
            }
        }
        """
        ),
        "utf-8",
    )
    tree = parser.parse(code)
    root_node = tree.root_node

    assert str(root_node) == (
        "(source_file "
        "(function_declaration "
        "name: (identifier) "
        "parameters: (parameter_list) "
        "body: (block "
        "(if_statement "
        "condition: (identifier) "
        "consequence: (block "
        "(expression_statement (call_expression "
        "function: (identifier) "
        "arguments: (argument_list))))))))"
    )
