import inspect
import re
from typing import Any

from sphinx.application import Sphinx
from sphinx.ext.autodoc import Options
from sphinx_autodoc_typehints import format_annotation, get_all_type_hints


def fix_screwed_up_return_info(
    app: Sphinx, what: str, name: str, obj: Any, lines: list[str]
) -> None:
    """If there is a "Returns" block in the docstring but it has only one line
    of info, napoleon will mess up and think it's the return type.

    Fix this by converting it from a ":rtype:" to a ":return:" and adding the
    correct :rtype: with sphinx_autodoc_typehints.format_annotation.
    """

    #  Find the rtype
    for at, line in enumerate(lines):
        if line.startswith(":rtype:"):
            at = at
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
    lines.insert(at, f":rtype: {formatted_annotation}")


LEADING_STAR_PAT = re.compile(r"(^\s*) \*")


def fix_bulleted_return_annotation(lines: list[str]) -> None:
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
            idx -= 1
            break
        # Remove bullet from rest of lines
        lines[idx] = LEADING_STAR_PAT.sub(r"\1", lines[idx])
    # Remove italicization of last line
    lines[idx] = " " + LEADING_STAR_PAT.sub(r"\1", lines[idx]).rstrip()[:-1]


def fix_constructor_arg_and_attr_same_name(
    app: Sphinx, what: str, name: str, obj: Any, lines: list[str]
) -> None:
    """Napoleon has a bug that causes it to grab type annotations for
    constructor args from attribute annotations.

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
    app: Sphinx,
    what: str,
    name: str,
    obj: Any,
    options: Options | None,
    lines: list[str],
) -> None:
    """sphinx_autodoc_typehints adds an :rtype: to properties even though IMO it
    is redundant. Undo this.

    Fixed upstream: https://github.com/tox-dev/sphinx-autodoc-typehints/pull/287
    """
    if inspect.isdatadescriptor(obj):
        lines[:] = [line for line in lines if not line.startswith(":rtype:")]

    if what in ["method", "function"]:
        fix_bulleted_return_annotation(lines)
        fix_screwed_up_return_info(app, what, name, obj, lines)
        # ensure_argument_types(app, what, name, obj, lines)

    if what == "class":
        fix_constructor_arg_and_attr_same_name(app, what, name, obj, lines)


__all__ = ["process_docstring"]
