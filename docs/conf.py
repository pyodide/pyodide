# -*- coding: utf-8 -*-
# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

import os
import sys
from typing import Dict, Any
import pathlib
import subprocess

base_dir = pathlib.Path(__file__).resolve().parent.parent
path_dirs = [
    str(base_dir),
    str(base_dir / "docs/sphinx_pyodide"),
    str(base_dir / "src/pyodide-py"),
    str(base_dir / "packages/micropip/micropip"),
]
sys.path = path_dirs + sys.path

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

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinxcontrib.napoleon",
    "myst_parser",
    "sphinx_js",
    "autodocsumm",
    "sphinx_pyodide",
    "sphinx_argparse_cli",
    "versionwarning.extension",
]

myst_enable_extensions = ["substitution"]
js_source_path = ["../src/", "../src/core"]
root_for_relative_js_paths = "../src/"

versionwarning_messages = {
    "latest": (
        "This is the development version of the documentation. ",
        'See <a href="https://pyodide.org/">here</a> for latest stable '
        "documentation. In particular, do not use Pyodide with non "
        "versionned (`dev`) URLs from the CDN for deployed applications.",
    )
}

autosummary_generate = True
autodoc_default_flags = ["members", "inherited-members"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
source_suffix = [".rst", ".md"]

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = None

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"
html_logo = "_static/img/pyodide-logo.png"
html_title = f"Version {version}"

# theme-specific options
html_theme_options: Dict[str, Any] = {}

# paths that contain custom static files (such as style sheets)
html_static_path = ["_static"]


html_css_files = [
    "css/pyodide.css",
]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
# html_sidebars = {}

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "Pyodidedoc"

# A list of files that should not be packed into the epub file.
epub_exclude_files = ["search.html"]

if "READTHEDOCS" in os.environ:
    env = {"PYODIDE_BASE_URL": "https://cdn.jsdelivr.net/pyodide/dev/full/"}
    os.makedirs("_build/html", exist_ok=True)
    res = subprocess.check_output(
        ["make", "-C", "..", "docs/_build/html/console.html"],
        env=env,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    print(res)
