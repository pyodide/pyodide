from .jsdoc import (
    patch_sphinx_js,
    ts_post_convert,
    ts_should_destructure_arg,
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


def setup(app):
    fix_pyodide_ffi_path()
    remove_property_prefix()
    patch_sphinx_js()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
    app.connect("builder-inited", add_mdn_xrefs)
    app.config.ts_post_convert = ts_post_convert
    app.config.ts_should_destructure_arg = ts_should_destructure_arg
    app.config.ts_type_xref_formatter = ts_xref_formatter
    app.config.ts_type_bold = True
