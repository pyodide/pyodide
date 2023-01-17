from sphinx.addnodes import desc_signature

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


def patch_py_attribute_handle_signature():
    """
    Patch PyAttribute.handle_signature so that it renders rst instead of
    escaping it.
    """
    from docutils import nodes
    from docutils.parsers.rst import Parser as RstParser
    from docutils.utils import new_document
    from sphinx import addnodes
    from sphinx.domains.python import PyAttribute

    def handle_signature(
        self: PyAttribute, sig: str, signode: desc_signature
    ) -> tuple[str, str]:
        """This changes the handling for types compared to upstream version.
        Parse rst in the type name instead of escaping it.

        The `if typ:` block is changed compared to upstream, rest is same.
        """
        fullname, prefix = super(PyAttribute, self).handle_signature(sig, signode)

        typ = self.options.get("type")
        if typ:
            settings = self.state.document.settings
            doc = new_document("", settings)
            RstParser().parse(typ, doc)
            # Remove top level paragraph node so that there is no line break.
            annotations = doc.children[0].children
            signode += addnodes.desc_annotation(
                typ,
                "",
                addnodes.desc_sig_punctuation("", ":"),
                addnodes.desc_sig_space(),
                *annotations
            )
        value = self.options.get("value")
        if value:
            signode += addnodes.desc_annotation(
                value,
                "",
                addnodes.desc_sig_space(),
                addnodes.desc_sig_punctuation("", "="),
                addnodes.desc_sig_space(),
                nodes.Text(value),
            )

        return fullname, prefix

    PyAttribute.handle_signature = handle_signature


def remove_property_prefix():
    """
    I don't think it is important to distinguish in the docs between properties
    and attributes. This removes the "property" prefix from properties.
    """
    from sphinx.domains.python import PyProperty

    def get_signature_prefix(self: PyProperty, sig: str) -> list[str]:
        return []

    PyProperty.get_signature_prefix = get_signature_prefix


def patch_attribute_documenter(app):
    """Instead of using stringify-typehint in
    `AttributeDocumenter.add_directive_header`, use `format_annotation`.
    """
    import sphinx.ext.autodoc
    from sphinx.ext.autodoc import AttributeDocumenter
    from sphinx_autodoc_typehints import format_annotation

    def stringify_typehint(annotation, *args, **kwargs):
        return format_annotation(annotation, app.config)

    orig_add_directive_header = AttributeDocumenter.add_directive_header

    def add_directive_header(*args, **kwargs):
        orig_stringify_typehint = sphinx.ext.autodoc.stringify_typehint
        sphinx.ext.autodoc.stringify_typehint = stringify_typehint
        result = orig_add_directive_header(*args, **kwargs)
        sphinx.ext.autodoc.stringify_typehint = orig_stringify_typehint
        return result

    AttributeDocumenter.add_directive_header = add_directive_header


def setup(app):
    patch_templates()
    patch_py_attribute_handle_signature()
    patch_attribute_documenter(app)
    remove_property_prefix()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
    from .napoleon_fixes import process_docstring

    app.connect("autodoc-process-docstring", process_docstring)
