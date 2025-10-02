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

panels_add_bootstrap_css = False

# -- Project information -----------------------------------------------------

project = "Pyodide"
author = "Pyodide contributors"
copyright = "2019-2024, Pyodide contributors and Mozilla"

suppress_warnings = ["config.cache"]
nitpicky = True
nitpick_ignore: list[tuple[str, str]] = []


def ignore_typevars():
    """These are all intentionally broken. Disable the warnings about it."""
    PY_TYPEVARS_TO_IGNORE = ("T", "T_co", "T_contra", "V_co", "KT", "VT", "VT_co", "P")
    JS_TYPEVARS_TO_IGNORE = ("TResult", "TResult1", "TResult2", "U")

    nitpick_ignore.extend(
        ("py:obj", f"_pyodide._core_docs.{typevar}")
        for typevar in PY_TYPEVARS_TO_IGNORE
    )
    nitpick_ignore.extend(("js:func", typevar) for typevar in JS_TYPEVARS_TO_IGNORE)


ignore_typevars()

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
    "sphinx_pyodide",
    "sphinx_argparse_cli",
    "sphinx_issues",
    "sphinx_autodoc_typehints",
    "sphinx_design",  # Used for tabs in building-from-sources.md
]


myst_enable_extensions = ["substitution", "attrs_inline"]

js_language = "typescript"
jsdoc_tsconfig_path = "../src/js/tsconfig.json"
root_for_relative_js_paths = "../src/"
issues_github_path = "pyodide/pyodide"

versionwarning_message = (
    "This is the development version of the documentation. "
    'See <a href="https://pyodide.org/">here</a> for latest stable '
    "documentation. Please do not use Pyodide with non "
    "versioned (`dev`) URLs from the CDN for deployed applications!"
)

autosummary_generate = True
autodoc_default_flags = ["members", "inherited-members"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.13", None),
    "micropip": ("https://micropip.pyodide.org/en/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# Add modules to be mocked.
mock_modules = ["tomli"]

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

html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"
html_logo = "_static/img/pyodide-logo.png"

# theme-specific options
html_theme_options: dict[str, Any] = {
    "announcement": "",
    "repository_url": "https://github.com/pyodide/pyodide",
    "use_repository_button": True,
}

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

# Try not to cause side effects if we are imported incidentally.

IN_SPHINX = "sphinx" in sys.modules and hasattr(sys.modules["sphinx"], "application")
IN_READTHEDOCS = "READTHEDOCS" in os.environ
IN_READTHEDOCS_LATEST = (
    IN_READTHEDOCS and os.environ.get("READTHEDOCS_VERSION") == "latest"
)


base_dir = Path(__file__).resolve().parent.parent
extra_sys_path_dirs = [
    str(base_dir),
    str(base_dir / "src/py"),
]


if IN_SPHINX:
    # sphinx_pyodide is imported before setup() is called because it's a sphinx
    # extension, so we need it to be on the path early. Everything else can be
    # added to the path in setup().
    #
    # TODO: pip install -e sphinx-pyodide instead.
    sys.path = [str(base_dir / "docs/sphinx_pyodide")] + sys.path


def patch_docs_argspec():
    import builtins

    from sphinx_pyodide.util import docs_argspec

    # override docs_argspec, _pyodide.docs_argspec will read this value back.
    # Must do this before importing pyodide!
    setattr(builtins, "--docs_argspec--", docs_argspec)


def patch_inspect():
    # Monkey patch for python3.11 incompatible code
    import inspect

    if not hasattr(inspect, "getargspec"):
        inspect.getargspec = inspect.getfullargspec  # type: ignore[attr-defined]


def prevent_parens_after_js_class_xrefs():
    from sphinx.domains.javascript import JavaScriptDomain, JSXRefRole

    JavaScriptDomain.roles["class"] = JSXRefRole()


def apply_patches():
    patch_docs_argspec()
    patch_inspect()
    prevent_parens_after_js_class_xrefs()


def calculate_pyodide_version(app):
    import pyodide

    config = app.config

    # The full version, including alpha/beta/rc tags.
    config.release = config.version = version = pyodide.__version__

    if ".dev" in version or os.environ.get("READTHEDOCS_VERSION") == "latest":
        CDN_URL = "https://cdn.jsdelivr.net/pyodide/dev/full/"
    else:
        CDN_URL = f"https://cdn.jsdelivr.net/pyodide/v{version}/full/"

    app.config.CDN_URL = CDN_URL
    app.config.html_title = f"Version {version}"

    app.config.global_replacements = {
        "{{PYODIDE_CDN_URL}}": CDN_URL,
        "{{VERSION}}": version,
    }


def set_announcement_message():
    html_theme_options["announcement"] = (
        versionwarning_message if IN_READTHEDOCS_LATEST else ""
    )


def write_console_html(app):
    # Make console.html file
    env = {"PYODIDE_BASE_URL": app.config.CDN_URL}
    os.makedirs(app.outdir, exist_ok=True)
    os.makedirs("../dist", exist_ok=True)
    res = subprocess.check_output(
        ["make", "-C", "..", "dist/console.html", "dist/console-v2.html"],
        env=env,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    print(res)

    # insert the Plausible analytics script to console.html
    console_html_lines = (
        Path("../dist/console.html").read_text().splitlines(keepends=True)
    )
    console_v2_html_lines = (
        Path("../dist/console-v2.html").read_text().splitlines(keepends=True)
    )

    def insert_analytics_script(html_lines):
        for idx, line in enumerate(list(html_lines)):
            if "</style>" in line:
                # insert the analytics script after the end of the inline CSS block
                html_lines.insert(
                    idx + 1,
                    "    <script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{\"token\": \"4405a86c36a84efca5dbde1b25edd153\"}'></script>\n",
                )
                break
        else:
            raise ValueError("Could not find a CSS block in the <head> section")

    insert_analytics_script(console_html_lines)
    insert_analytics_script(console_v2_html_lines)

    output_path = Path(app.outdir) / "console.html"
    output_path.write_text("".join(console_html_lines))

    v2_output_path = Path(app.outdir) / "console-v2.html"
    v2_output_path.write_text("".join(console_v2_html_lines))

    def remove_console_html():
        Path("../dist/console.html").unlink(missing_ok=True)
        Path("../dist/console-v2.html").unlink(missing_ok=True)

    atexit.register(remove_console_html)


def write_examples(app):
    """Preprocess the examples HTML/ js files and copy them to the output directory"""
    example_outdir = Path(app.outdir) / "examples"
    example_outdir.mkdir(exist_ok=True, parents=True)

    example_html_dir = Path("./usage/examples")

    for example in example_html_dir.iterdir():
        if not example.is_file() or example.suffix not in [".html", ".js"]:
            continue
        text = example.read_text()
        text = text.replace("{{ PYODIDE_BASE_URL }}", app.config.CDN_URL)

        output_path = example_outdir / example.name
        output_path.write_text(text)


def ensure_typedoc_on_path():
    if shutil.which("typedoc"):
        return
    typedoc_dir = Path("../src/js/node_modules/.bin").resolve()
    os.environ["PATH"] += ":" + str(typedoc_dir)
    print(os.environ["PATH"])
    if shutil.which("typedoc"):
        return
    if IN_READTHEDOCS:
        subprocess.run(["npm", "ci"], cwd="../src/js", check=True)
        Path("../node_modules").symlink_to("../src/js/node_modules")
    if shutil.which("typedoc"):
        return
    raise Exception(
        "Before building the Pyodide docs you must run 'npm install' in 'src/js'."
    )


def prune_webloop_docs():
    # Prevent API docs for webloop methods: they are the same as for base event loop
    # and it clutters api docs too much
    from sphinx_pyodide.util import delete_attrs

    import pyodide.console
    import pyodide.webloop

    delete_attrs(pyodide.webloop.WebLoop)
    delete_attrs(pyodide.webloop.WebLoopPolicy)
    delete_attrs(pyodide.console.PyodideConsole)

    for module in mock_modules:
        sys.modules[module] = mock.Mock()


def prune_jsproxy_constructor_docs():
    from pyodide.ffi import JsProxy

    del JsProxy.__new__


def prune_docs():
    prune_webloop_docs()
    prune_jsproxy_constructor_docs()


# https://github.com/sphinx-doc/sphinx/issues/4054
def global_replace(app, docname, source):
    result = source[0]
    for key in app.config.global_replacements:
        result = result.replace(key, app.config.global_replacements[key])
    source[0] = result


always_document_param_types = True


def typehints_formatter(annotation, config):  # noqa: PLR0911
    """Adjust the rendering of various types that sphinx_autodoc_typehints mishandles"""
    from sphinx_autodoc_typehints import (
        get_annotation_class_name,
        get_annotation_module,
    )

    try:
        module = get_annotation_module(annotation)
        class_name = get_annotation_class_name(annotation, module)
    except ValueError:
        assert annotation == Ellipsis
        return None
    full_name = f"{module}.{class_name}"
    if full_name == "typing.TypeVar":
        # The way sphinx-autodoc-typehints renders TypeVar is too noisy for my
        # taste
        return f"``{annotation.__name__}``"
    if full_name == "ast.Module":
        return "`Module <https://docs.python.org/3/library/ast.html#module-ast>`_"
    # TODO: perhaps a more consistent way to handle JS xrefs / type annotations?
    if full_name == "pyodide.http._pyfetch.AbortController":
        return ":js:class:`AbortController`"
    if full_name == "pyodide.http._pyfetch.AbortSignal":
        return ":js:class:`AbortSignal`"
    if full_name == "pyodide.http.pyfetch.Request":
        return ":js:class:`Request`"
    return None


def setup(app):
    sys.path = extra_sys_path_dirs + sys.path
    app.add_config_value("global_replacements", {}, True)
    app.add_config_value("CDN_URL", "", True)
    files = []
    for dir in ["core", "js"]:
        files += [str(x) for x in (Path("../src") / dir).glob("*.ts")]
    app.config.js_source_path = files
    app.connect("source-read", global_replace)

    set_announcement_message()
    apply_patches()
    calculate_pyodide_version(app)
    ensure_typedoc_on_path()
    write_console_html(app)
    write_examples(app)
    prune_docs()
    Path("../src/js/generated/pyproxy.ts").unlink(missing_ok=True)
