from .autodoc_submodules import monkeypatch_module_documenter
from .jsdoc import (
    PyodideAnalyzer,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
)
from .lexers import HtmlPyodideLexer, PyodideLexer
from .packages import get_packages_summary_directive


def wrap_analyzer(app):
    app._sphinxjs_analyzer = PyodideAnalyzer(app._sphinxjs_analyzer)


def patch_templates():
    """Patch in a different jinja2 loader so we can override templates with our
    own versions.
    """
    from pathlib import Path

    from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader
    from sphinx_js.analyzer_utils import dotted_path
    from sphinx_js.renderers import JsRenderer

    loader = ChoiceLoader(
        [
            FileSystemLoader(Path(__file__).parent / "templates"),
            PackageLoader("sphinx_js", "templates"),
        ]
    )
    env = Environment(loader=loader)

    def patched_rst_method(self, partial_path, obj, use_short_name=False):
        """Return rendered RST about an entity with the given name and IR
        object."""
        dotted_name = partial_path[-1] if use_short_name else dotted_path(partial_path)

        # Render to RST using Jinja:
        template = env.get_template(self._template)
        return template.render(**self._template_vars(dotted_name, obj))

    JsRenderer.rst = patched_rst_method


def setup(app):
    patch_templates()
    monkeypatch_module_documenter()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
