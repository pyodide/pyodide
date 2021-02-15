# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

for base_path in [".", ".."]:
    sys.path.insert(0, os.path.abspath(base_path))
    sys.path.insert(1, os.path.abspath(os.path.join(base_path, "src", "pyodide-py")))
    sys.path.insert(
        2, os.path.abspath(os.path.join(base_path, "packages", "micropip", "micropip"))
    )

# -- Project information -----------------------------------------------------

project = "Pyodide"
copyright = "2019, Mozilla"
author = "Mozilla"

import pyodide
import micropip  # noqa

# The full version, including alpha/beta/rc tags.
release = version = pyodide.__version__


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinxcontrib.napoleon",
    "myst_parser",
    "sphinx_js",
]

js_source_path = "../src/"

autosummary_generate = True
autodoc_default_flags = ["members", "inherited-members"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = [".rst", ".md"]

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = None


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    # Toc options
    "collapse_navigation": True,
    "sticky_navigation": True,
    "navigation_depth": 2,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}


# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "Pyodidedoc"


# -- Options for Epub output -------------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ''

# A unique identification for the text.
#
# epub_uid = ''

# A list of files that should not be packed into the epub file.
epub_exclude_files = ["search.html"]

from pygments.lexer import bygroups, inherit, using
from pygments.lexers import PythonLexer
from pygments.lexers.javascript import JavascriptLexer
from pygments.lexers.html import HtmlLexer
from pygments.token import *


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


def setup(app):
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
