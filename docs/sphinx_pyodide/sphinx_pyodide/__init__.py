from .jsdoc import (
    PyodideAnalyzer,
    get_jsdoc_content_directive,
    get_jsdoc_summary_directive,
)
from .lexers import HtmlPyodideLexer, PyodideLexer
from .mdn_xrefs import add_mdn_xrefs
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


def fix_pyodide_ffi_path():
    """
    The `pyodide.ffi` stuff is defined in `_pyodide._core_docs`. We don't want
    `_pyodide._core_docs` to appear in the documentation because this isn't
    where you should import things from so we override the `__name__` of
    `_pyodide._core_docs` to be `pyodide.ffi`. But then Sphinx fails to locate
    the source for the stuff defined in `_pyodide._core_docs`.

    This patches `ModuleAnalyzer` to tell it to look for the source of things
    from `pyodide.ffi` in `_pyodide._core_docs`.
    """
    from sphinx.ext.autodoc import ModuleAnalyzer

    orig_for_module = ModuleAnalyzer.for_module.__func__

    @classmethod  # type: ignore[misc]
    def for_module(cls: type, modname: str) -> ModuleAnalyzer:
        if modname == "pyodide.ffi":
            modname = "_pyodide._core_docs"
        return orig_for_module(cls, modname)

    ModuleAnalyzer.for_module = for_module


def remove_property_prefix():
    """
    I don't think it is important to distinguish in the docs between properties
    and attributes. This removes the "property" prefix from properties.
    """
    from sphinx.domains.python import PyProperty

    def get_signature_prefix(self: PyProperty, sig: str) -> list[str]:
        return []

    PyProperty.get_signature_prefix = get_signature_prefix


def setup(app):
    patch_templates()
    fix_pyodide_ffi_path()
    remove_property_prefix()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
    app.connect("builder-inited", add_mdn_xrefs)
