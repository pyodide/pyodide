from pathlib import Path

from sphinx.addnodes import desc_signature
from sphinx_js import renderers

from .jsdoc import (
    patch_sphinx_js,
    ts_xref_formatter,
)
from .lexers import HtmlPyodideLexer, PyodideLexer
from .mdn_xrefs import add_mdn_xrefs
from .packages import get_packages_summary_directive


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


def remove_js_module_prefix():
    from sphinx.domains.javascript import JSObject

    orig_handle_signature = JSObject.handle_signature

    def handle_signature(self: JSObject, sig: str, signode: desc_signature) -> None:
        orig_ref_context = self.env.ref_context
        new_ref_context = orig_ref_context.copy()
        objtype = signode.parent.get("objtype")
        mod = new_ref_context.get("js:module")
        if mod == "exports" or objtype in {"interface", "typealias"}:
            # Remove module prefix.
            new_ref_context["js:module"] = None
        try:
            self.env.ref_context = new_ref_context
            return orig_handle_signature(self, sig, signode)
        finally:
            self.env.ref_context = orig_ref_context

    JSObject.handle_signature = handle_signature


def setup(app):
    fix_pyodide_ffi_path()
    remove_property_prefix()
    patch_sphinx_js()
    remove_js_module_prefix()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
    app.connect("builder-inited", add_mdn_xrefs)
    app.config.ts_type_xref_formatter = ts_xref_formatter
    app.config.ts_type_bold = True
    app.config.ts_sphinx_js_config = Path(__file__).parent / "sphinxJsConfig.ts"
    renderers._SECTION_ORDER = [
        "type_aliases",
        "interfaces",
        "attributes",
        "functions",
        "classes",
    ]
