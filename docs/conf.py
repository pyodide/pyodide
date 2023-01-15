# Configuration file for the Sphinx documentation builder.

# -- Path setup --------------------------------------------------------------

import atexit
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import micropip

panels_add_bootstrap_css = False

# -- Project information -----------------------------------------------------

project = "Pyodide"
copyright = "2019-2022, Pyodide contributors and Mozilla"
pyodide_version = "0.22.0"

if ".dev" in pyodide_version or os.environ.get("READTHEDOCS_VERSION") == "latest":
    CDN_URL = "https://cdn.jsdelivr.net/pyodide/dev/full/"
else:
    CDN_URL = f"https://cdn.jsdelivr.net/pyodide/v{pyodide_version}/full/"

# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_js",
    "sphinx_click",
    "autodocsumm",
    "sphinx_panels",
    "sphinx_pyodide",
    "sphinx_argparse_cli",
    "versionwarning.extension",
    "sphinx_issues",
    "sphinx_autodoc_typehints",
]


myst_enable_extensions = ["substitution"]

js_language = "typescript"
jsdoc_config_path = "../src/js/tsconfig.json"
root_for_relative_js_paths = "../src/"
issues_github_path = "pyodide/pyodide"

versionwarning_messages = {
    "latest": (
        "This is the development version of the documentation. "
        'See <a href="https://pyodide.org/">here</a> for latest stable '
        "documentation. Please do not use Pyodide with non "
        "versioned (`dev`) URLs from the CDN for deployed applications!"
    )
}
versionwarning_body_selector = "#main-content > div"

autosummary_generate = True
autodoc_default_flags = ["members", "inherited-members"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.10", None),
    "micropip": (f"https://micropip.pyodide.org/en/v{micropip.__version__}/", None),
}

# Add modules to be mocked.
mock_modules = ["ruamel.yaml", "tomli"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
source_suffix = [".rst", ".md"]

# The master toctree document.
master_doc = "index"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "README.md",
    "sphinx_pyodide",
    ".*",
]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = None

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"
html_logo = "_static/img/pyodide-logo.png"

# theme-specific options
html_theme_options: dict[str, Any] = {}

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


def delete_attrs(cls):
    """Prevent attributes of a class or module from being documented.

    The top level documentation comment of the class or module will still be
    rendered.
    """
    for name in dir(cls):
        if not name.startswith("_"):
            try:
                delattr(cls, name)
            except Exception:
                pass


# Try not to cause side effects if we are imported incidentally.

try:
    import sphinx

    IN_SPHINX = hasattr(sphinx, "application")
except ImportError:
    IN_SPHINX = False

IN_READTHEDOCS = "READTHEDOCS" in os.environ

if IN_READTHEDOCS:
    env = {"PYODIDE_BASE_URL": CDN_URL}
    os.makedirs("_build/html", exist_ok=True)
    res = subprocess.check_output(
        ["make", "-C", "..", "docs/_build/html/console.html"],
        env=env,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    print(res)
    # insert the Plausible analytics script to console.html
    console_path = Path("_build/html/console.html")
    console_html = console_path.read_text().splitlines(keepends=True)
    for idx, line in enumerate(list(console_html)):
        if 'pyodide.js">' in line:
            # insert the analytics script after the `pyodide.js` script
            console_html.insert(
                idx,
                '<script defer data-domain="pyodide.org" src="https://plausible.io/js/plausible.js"></script>\n',
            )
            break
    else:
        raise ValueError("Could not find pyodide.js in the <head> section")
    console_path.write_text("".join(console_html))


if IN_SPHINX:
    # Compatibility shims. sphinx-js and sphinxcontrib-napoleon have not been updated for Python 3.10
    import collections
    from typing import Callable, Mapping

    collections.Mapping = Mapping  # type: ignore[attr-defined]
    collections.Callable = Callable  # type: ignore[attr-defined]

    base_dir = Path(__file__).resolve().parent.parent
    path_dirs = [
        str(base_dir),
        str(base_dir / "pyodide-build"),
        str(base_dir / "docs/sphinx_pyodide"),
        str(base_dir / "src/py"),
        str(base_dir / "packages/micropip/src"),
    ]
    sys.path = path_dirs + sys.path

    from sphinx.domains.javascript import JavaScriptDomain, JSXRefRole

    JavaScriptDomain.roles["func"] = JSXRefRole()

    import micropip  # noqa: F401
    import pyodide
    from pyodide.ffi import JsProxy

    del JsProxy.__new__

    # The full version, including alpha/beta/rc tags.
    release = version = pyodide.__version__
    html_title = f"Version {version}"

    shutil.copy("../src/core/pyproxy.ts", "../src/js/pyproxy.gen.ts")
    shutil.copy("../src/core/error_handling.ts", "../src/js/error_handling.gen.ts")
    js_source_path = [str(x) for x in Path("../src/js").glob("*.ts")]

    def remove_pyproxy_gen_ts():
        Path("../src/js/pyproxy.gen.ts").unlink(missing_ok=True)

    atexit.register(remove_pyproxy_gen_ts)

    os.environ["PATH"] += f':{str(Path("../src/js/node_modules/.bin").resolve())}'
    print(os.environ["PATH"])
    if IN_READTHEDOCS:
        subprocess.run(["npm", "ci"], cwd="../src/js")
    elif not shutil.which("typedoc"):
        raise Exception(
            "Before building the Pyodide docs you must run 'npm install' in 'src/js'."
        )

    # Prevent API docs for webloop methods: they are the same as for base event loop
    # and it clutters api docs too much
    import pyodide.console
    import pyodide.webloop

    delete_attrs(pyodide.webloop.WebLoop)
    delete_attrs(pyodide.webloop.WebLoopPolicy)
    delete_attrs(pyodide.console.PyodideConsole)

    for module in mock_modules:
        sys.modules[module] = mock.Mock()


# https://github.com/sphinx-doc/sphinx/issues/4054
def globalReplace(app, docname, source):
    result = source[0]
    for key in app.config.global_replacements:
        result = result.replace(key, app.config.global_replacements[key])
    source[0] = result


global_replacements = {"{{PYODIDE_CDN_URL}}": CDN_URL}

from sphinx_autodoc_typehints import format_annotation

def typehints_formatter(annotation, config):
    """Adjust the rendering of Literal types.

    The literal values should be ``rendered as code``.
    """
    from sphinx_autodoc_typehints import (
        get_annotation_args,
        get_annotation_class_name,
        get_annotation_module,
    )

    try:
        module = get_annotation_module(annotation)
        class_name = get_annotation_class_name(annotation, module)
        args = get_annotation_args(annotation, module, class_name)
    except ValueError:
        return None
    if module == "_io":
        module = "io"
    full_name = f"{module}.{class_name}"
    if full_name == "typing.Literal":
        formatted_args = "\\[{}]".format(
            ", ".join("``{}``".format(repr(arg)) for arg in args)
        )
        return f":py:data:`~{full_name}`{formatted_args}"
    if full_name == "builtins.code":
        return ":py:class:`~types.CodeType`"
    if full_name == "ast.Module":
        return "`ast.Module <https://docs.python.org/3.10/library/ast.html>`_"
    if full_name == "collections.abc.Callable" and args and args[0] is not ...:
        fmt = [format_annotation(arg, config) for arg in args]
        return f":py:class:`~{full_name}`\\[\\[{', '.join(fmt[:-1])}], {fmt[-1]}]"
    if full_name == "collections.abc.Callable" and args:
        fmt = [format_annotation(arg, config) for arg in args]
        return f":py:class:`~{full_name}`\\[{', '.join(fmt)}]"
    if module == "io":
        return f":py:class:`~{full_name}`"
    return None


def setup(app):
    app.add_config_value("global_replacements", {}, True)
    app.connect("source-read", globalReplace)
