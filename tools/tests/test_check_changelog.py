import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[1]))
from check_changelog import find_missing_references

BASE = """\
# Change Log

## Unreleased

### General

- {{ Fix }} Existing entry.
  {pr}`1234`

## Version 0.1.0

- {{ Fix }} Old entry without a reference.
"""


def add_entries(text: str, entries: str) -> str:
    return text.replace("### General\n\n", f"### General\n\n{entries}\n", 1)


def test_new_entries():
    text = add_entries(
        BASE,
        """\
- {{ Fix }} Has a PR reference.
  {pr}`1`

- {{ Fix }} Has an issue reference in the middle {issue}`2` of the text.

- {{ Enhancement }} The reference is in a sub-item.
  - Sub item {pr}`3`

- {{ Fix }} Missing a reference,
  spanning multiple lines.
""",
    )
    assert find_missing_references(BASE, text) == [
        "- {{ Fix }} Missing a reference, spanning multiple lines."
    ]


def test_reference_requires_number():
    text = add_entries(BASE, "- {{ Fix }} Placeholder {pr}`XXXX`\n")
    assert len(find_missing_references(BASE, text)) == 1


def test_existing_entries_are_not_checked():
    assert find_missing_references(BASE, BASE) == []


def test_rewrapped_entry_is_not_new():
    text = BASE.replace(
        "- {{ Fix }} Old entry without a reference.",
        "- {{ Fix }} Old entry\n  without a reference.",
    )
    assert find_missing_references(BASE, text) == []


def test_release():
    text = BASE.replace("## Unreleased", "## Version 0.2.0")
    assert find_missing_references(BASE, text) == []
