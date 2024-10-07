from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tree-sitter-java"])
def test_tree_sitter_java(selenium):
    import textwrap

    import tree_sitter_java
    from tree_sitter import Language, Parser

    JAV_LANGUAGE = Language(tree_sitter_java.language())
    parser = Parser(JAV_LANGUAGE)

    code = bytes(
        textwrap.dedent(
            """
        void foo() {
            if (bar) {
                baz();
            }
        }
        """
        ),
        "utf-8",
    )
    tree = parser.parse(code)
    root_node = tree.root_node

    assert str(root_node) == (
        "(program "
        "(method_declaration "
        "type: (void_type) "
        "name: (identifier) "
        "parameters: (formal_parameters) "
        "body: (block "
        "(if_statement "
        "condition: (parenthesized_expression (identifier)) "
        "consequence: (block "
        "(expression_statement (method_invocation "
        "name: (identifier) "
        "arguments: (argument_list))))))))"
    )
