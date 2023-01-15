import inspect
import re
from typing import Any

from sphinx_autodoc_typehints import format_annotation, get_all_type_hints

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


def handle_screwed_up_return_info(app, what, name, obj, options, lines):
    """If there is a "Returns" block in the docstring but it has only one line
    of info, napoleon will mess up and think it's the return type.

    Fix this by converting it from a ":rtype:" to a ":return:" and adding the
    correct :rtype: with sphinx_autodoc_typehints.format_annotation.
    """

    #  Find the rtype
    for at, line in enumerate(lines):
        if line.startswith(":rtype:"):
            idx = at
            break
    else:
        return

    # Calculate the correct value
    type_hints = get_all_type_hints(app.config.autodoc_mock_imports, obj, name)
    if "return" not in type_hints:
        return
    formatted_annotation = format_annotation(type_hints["return"], app.config)

    # Sometimes the rtype is already right. Don't double it up!
    if lines[at] == f":rtype: {formatted_annotation}":
        return
    # Convert current :rtype: into a :return: and add a new :rtype: with the
    # calculated contents.
    lines[at] = line.replace(":rtype:", ":return:")
    lines.insert(idx, f":rtype: {formatted_annotation}")


def ensure_argument_types(app, what, name, obj, options, lines):
    """If there is no Parameters section at all, this adds type
    annotations for all the arguments.
    """
    for at, line in enumerate(lines):
        if line.startswith(":param"):
            return
        if line.startswith(("..", ":return", ":rtype")):
            at = at
            break
    type_hints = get_all_type_hints(app.config.autodoc_mock_imports, obj, name)
    to_add = [""]
    type_hints.pop("return", None)
    for (key, value) in type_hints.items():
        formatted_annotation = format_annotation(value, app.config)
        to_add.append(f":type {key}: {formatted_annotation}")
        to_add.append(f":param {key}:")

    lines[at:at] = to_add


LEADING_STAR_PAT = re.compile(r"(^\s*)\*")


def handle_bulleted_return_annotation(app, what, name, obj, options, lines):
    """
    For some reason autodoc messes up the rendering of return value annotations:
    if the annotation takes up multiple lines, it displays it as a bulleted list
    with the last bullet italicized. This removes the bullet and the
    italicization of the last line.
    """
    for idx, line in enumerate(lines):
        if line.startswith(":returns:"):
            cur = idx
            break
    else:
        return
    line = line.removeprefix(":returns:").strip()
    if not line.startswith("*"):
        return
    if line.startswith("* **"):
        return
    # Remove bullet from first line
    lines[cur] = lines[cur].replace(":returns: *", ":returns:")
    for idx in range(cur + 1, len(lines)):
        if lines[idx].strip() == "":
            break
        # Remove bullet from rest of lines
        lines[idx] = LEADING_STAR_PAT.sub(r"\1", lines[idx])
    # Remove italicization of last line
    lines[idx - 1] = LEADING_STAR_PAT.sub(r"\1", lines[idx - 1]).rstrip()[:-1]


def fix_constructor_arg_and_attr_same_name(app, what, name, obj, options, lines):
    """Napoleon has a bug that causes it to grab type annotations for
    constructor args from

    https://github.com/sphinx-doc/sphinx/pull/11131
    """
    cons_type_hints = get_all_type_hints(
        app.config.autodoc_mock_imports, obj.__init__, name
    )
    attrs_type_hints = get_all_type_hints(app.config.autodoc_mock_imports, obj, name)
    for (key, value) in cons_type_hints.items():
        if key not in attrs_type_hints:
            continue
        for at, line in enumerate(lines):
            if line.startswith(f":type {key}:"):
                at = at
                break
        else:
            continue
        formatted_annotation = format_annotation(value, app.config)
        lines[:] = [line for line in lines if not line.startswith(f":type {key}:")]
        lines.insert(at, f":type {key}: {formatted_annotation}")


def process_docstring(
    app: Any,
    what: str,
    name: str,
    obj: Any,
    options: Any,
    lines: list[str],  # noqa: U100
) -> None:
    """sphinx_autodoc_typehints adds an :rtype: to properties even though IMO it
    is redundant. Undo this.

    Fixed upstream: https://github.com/tox-dev/sphinx-autodoc-typehints/pull/287
    """
    if inspect.isdatadescriptor(obj):
        lines[:] = [line for line in lines if not line.startswith(":rtype:")]

    if what in ["method", "function"]:
        handle_bulleted_return_annotation(app, what, name, obj, options, lines)
        handle_screwed_up_return_info(app, what, name, obj, options, lines)
        ensure_argument_types(app, what, name, obj, options, lines)

    if what == "class":
        fix_constructor_arg_and_attr_same_name(app, what, name, obj, options, lines)


def setup(app):
    patch_templates()
    app.add_lexer("pyodide", PyodideLexer)
    app.add_lexer("html-pyodide", HtmlPyodideLexer)
    app.setup_extension("sphinx_js")
    app.connect("builder-inited", wrap_analyzer)
    app.add_directive("js-doc-summary", get_jsdoc_summary_directive(app))
    app.add_directive("js-doc-content", get_jsdoc_content_directive(app))
    app.add_directive("pyodide-package-list", get_packages_summary_directive(app))
    app.connect("autodoc-process-docstring", process_docstring)
