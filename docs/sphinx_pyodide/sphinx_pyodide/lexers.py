from pygments.lexer import bygroups, inherit, using, default
from pygments.lexers import PythonLexer
from pygments.lexers.javascript import JavascriptLexer
from pygments.lexers.html import HtmlLexer
from pygments.token import Name, Punctuation, Text, Token


class PyodideLexer(JavascriptLexer):
    tokens = {
        "root": [
            (
                r"(pyodide)(\.)(runPython|runPythonAsync)(\()",
                bygroups(
                    Token.Name,
                    Token.Operator,
                    Token.Name,
                    Token.Punctuation,
                ),
                "python-code",
            ),
            inherit,
        ],
        "python-code": [
            (
                rf"({quotemark})((?:\\\\|\\[^\\]|[^{quotemark}\\])*)({quotemark})",
                bygroups(
                    Token.Literal.String, using(PythonLexer), Token.Literal.String
                ),
                "#pop",
            )
            for quotemark in ["'", '"', "`"]
        ]
        + [default("#pop")],
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
