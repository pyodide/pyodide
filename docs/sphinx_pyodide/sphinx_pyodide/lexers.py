from pygments.lexer import bygroups, inherit, using
from pygments.lexers import PythonLexer
from pygments.lexers.javascript import JavascriptLexer
from pygments.lexers.html import HtmlLexer
from pygments.token import Name, Punctuation, Text, Token


class PyodideLexer(JavascriptLexer):
    tokens = {
        "root": [
            (
                rf"""(pyodide)(\.)(runPython|runPythonAsync)(\()(`)""",
                bygroups(
                    Token.Name,
                    Token.Operator,
                    Token.Name,
                    Token.Punctuation,
                    Token.Literal.String.Single,
                ),
                "python-code",
            ),
            inherit,
        ],
        "python-code": [
            (
                r"(.+?)(`)(\))",
                bygroups(
                    using(PythonLexer), Token.Literal.String.Single, Token.Punctuation
                ),
                "#pop",
            )
        ],
    }


class HtmlPyodideLexer(HtmlLexer):
    tokens = {
        "script-content": [
            (
                r"(<)(\s*)(/)(\s*)(script)(\s*)(>)",
                bygroups(
                    Punctuation, Text, Punctuation, Text, Name.Tag, Text, Punctuation
                ),
                "#pop",
            ),
            (r".+?(?=<\s*/\s*script\s*>)", using(PyodideLexer)),
            (r".+?\n", using(PyodideLexer), "#pop"),
            (r".+", using(PyodideLexer), "#pop"),
        ],
    }
