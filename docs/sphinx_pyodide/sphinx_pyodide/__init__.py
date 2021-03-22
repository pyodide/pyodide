from .jsdoc import PyodideAnalyzer
from .lexers import PyodideLexer, HtmlPyodideLexer
from .jsdoc import get_jsdoc_summary_directive, get_jsdoc_content_directive
import traceback


def wrap_analyzer(app):
    try:
        app._sphinxjs_analyzer = PyodideAnalyzer(app._sphinxjs_analyzer)
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        import sys

        sys.exit(1)


def setup(app):
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
