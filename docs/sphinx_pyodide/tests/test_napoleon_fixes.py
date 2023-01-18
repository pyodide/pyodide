from textwrap import dedent
from typing import Callable, TypeVar
from unittest.mock import create_autospec

import pytest
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx_pyodide.napoleon_fixes import (
    fix_bulleted_return_annotation,
    fix_constructor_arg_and_attr_same_name,
    fix_screwed_up_return_info,
)

config = create_autospec(
    Config,
    typehints_fully_qualified=False,
    simplify_optional_unions=False,
    typehints_formatter=None,
    autodoc_mock_imports=[],
    _annotation_globals=globals(),
)
app: Sphinx = create_autospec(Sphinx, config=config)


@pytest.mark.parametrize(
    "orig",
    [
        pytest.param(
            """\
            Executes ``self.code``.

            Can only be used after calling compile.

            :param globals: The global scope in which to execute code. This is used as the ``globals``
                            parameter for :any:`exec`. If ``globals`` is absent, a new empty dictionary is used.

            :returns: * If the last nonwhitespace character of ``source`` is a semicolon,
                      * return ``None``. If the last statement is an expression, return the
                      * result of the expression. Use the ``return_mode`` and
                      * ``quiet_trailing_semicolon`` parameters to modify this default
                      * *behavior.*
            """,
            id="compile",
        )
    ],
)
def test_fix_bulleted_return_annotation(orig: str) -> None:
    orig = dedent(orig)
    processed_lines = orig.splitlines()
    fix_bulleted_return_annotation(processed_lines)

    assert (
        "\n".join(processed_lines).strip()
        == orig.replace("* ", "").replace("*", "").strip()
    )


@pytest.mark.parametrize(
    "orig",
    [
        pytest.param(
            """\
            Use Python's rlcompleter to complete the source string using the :any:`globals <Console.globals>` namespace.

            Finds last "word" in the source string and completes it with rlcompleter.

            :returns: * **completions** (*List[str]*) -- A list of completion strings.
                      * **start** (*int*) -- The index where completion starts.
            """,
            id="complete",
        ),
        pytest.param(
            """\
            Executes ``self.code``.

            Can only be used after calling compile.

            :param globals: The global scope in which to execute code. This is used as the ``globals``
                            parameter for :any:`exec`. If ``globals`` is absent, a new empty dictionary is used.

            :returns: If the last nonwhitespace character of ``source`` is a semicolon,
                      return ``None``. If the last statement is an expression, return the
                      result of the expression. Use the ``return_mode`` and
                      ``quiet_trailing_semicolon`` parameters to modify this default
                      behavior.
            """,
            id="no-stars",
        ),
    ],
)
def test_fix_bulleted_return_annotation_unmodified(orig):
    orig = dedent(orig)
    lines = orig.splitlines()
    fix_bulleted_return_annotation(lines)
    assert "\n".join(lines).strip() == orig.strip()


T = TypeVar("T")


def fixed_doc(new_doc: str) -> Callable[[T], T]:
    def dec(func):
        func.FIXED_DOC = new_doc
        return func

    return dec


def unchanged_doc(func: T) -> T:
    func.FIXED_DOC = func.__doc__  # type:ignore[attr-defined]
    return func


@fixed_doc(
    """\
    Summary info

    :rtype: :py:class:`int`
    :return: Some info about the return value
    """
)
def incorrect_rtype() -> int:
    """
    Summary info

    :rtype: Some info about the return value
    """
    return 6


@unchanged_doc
def correct_rtype() -> int:
    """
    Summary info

    :rtype: :py:class:`int`
    """
    return 6


@pytest.mark.parametrize("func", [incorrect_rtype, correct_rtype])
def test_fix_screwed_up_return_info(func):
    doc = dedent(func.__doc__)
    lines = doc.splitlines()
    fix_screwed_up_return_info(app, "function", func.__name__, func, lines)
    assert "\n".join(lines).strip() == dedent(func.FIXED_DOC).strip()


@fixed_doc(
    """\
    A Class

    :param blah: Description of parameter blah
    :type blah: :py:data:`~typing.Optional`\\[:py:class:`int`]
    """
)
class Blah:
    """
    A Class

    :param blah: Description of parameter blah
    :type blah: int
    """

    def __init__(self, blah: int | None):
        pass

    blah: int


@pytest.mark.parametrize("cls", [Blah])
def test_fix_constructor_arg_and_attr_same_name(cls):
    doc = dedent(cls.__doc__)
    lines = doc.splitlines()
    fix_constructor_arg_and_attr_same_name(app, "class", cls.__name__, cls, lines)
    assert "\n".join(lines).strip() == dedent(cls.FIXED_DOC).strip()
