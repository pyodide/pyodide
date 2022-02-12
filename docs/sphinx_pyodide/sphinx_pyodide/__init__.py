from .jsdoc import PyodideAnalyzer
from .lexers import PyodideLexer, HtmlPyodideLexer
from .jsdoc import get_jsdoc_summary_directive, get_jsdoc_content_directive
from .packages import get_packages_summary_directive
from .autodoc_submodules import monkeypatch_module_documenter


def wrap_analyzer(app):
    app._sphinxjs_analyzer = PyodideAnalyzer(app._sphinxjs_analyzer)


def setup(app):
    monkeypatch_module_documenter()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
