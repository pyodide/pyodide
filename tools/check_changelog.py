#!/usr/bin/env python3

# Check that every changelog entry added since BASE has a {pr} or {issue}
# reference. Existing entries are not checked because some of them predate
# this convention.
# Usage:
#   check_changelog.py BASE [changelog]
# e.g.
#   check_changelog.py upstream/main

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CHANGELOG = Path("docs/project/changelog.md")

# A top-level entry starts with "- " at column 0 and runs until the next
# top-level entry or heading.
ENTRY_START = re.compile(r"^(?=- |#)", re.M)
REFERENCE = re.compile(r"\{(pr|issue)\}`\d+`")


def get_entries(text: str) -> list[str]:
    """Return the top-level entries of the changelog with whitespace normalized."""
    return [" ".join(e.split()) for e in ENTRY_START.split(text) if e.startswith("- ")]


def find_missing_references(base_text: str, text: str) -> list[str]:
    """Return the entries not in base_text that have no {pr} or {issue} reference."""
    base_entries = set(get_entries(base_text))
    return [
        e
        for e in get_entries(text)
        if e not in base_entries and not REFERENCE.search(e)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that new changelog entries have a {pr} or {issue} reference"
    )
    parser.add_argument("base", help="git revision to compare against")
    parser.add_argument("changelog", nargs="?", type=Path, default=CHANGELOG)
    args = parser.parse_args()

    base_text = subprocess.run(
        ["git", "show", f"{args.base}:{args.changelog.as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    text = (ROOT / args.changelog).read_text()

    missing = find_missing_references(base_text, text)
    for entry in missing:
        print(
            f"::error file={args.changelog}::"
            f"Missing {{pr}} or {{issue}} reference: {entry[:80]}"
        )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
