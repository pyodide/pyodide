#!/usr/bin/env python3
import argparse
import difflib
import sys
from pathlib import Path

from sphinx.ext.intersphinx import fetch_inventory

PYODIDE_ROOT = Path(__file__).parents[1]
DOCS_DIR = PYODIDE_ROOT / "docs"
EXPECTED_DOCS_FILE = DOCS_DIR / "expected_js_docs.txt"


class App:
    srcdir = DOCS_DIR / "_build/html/"
    config = None


def check_list():
    inv = fetch_inventory(App, "https://example.com", "objects.inv")
    res = []
    for category, entries in inv.items():
        if entries is None:
            continue
        if not category.startswith("js"):
            continue
        res.append(category)
        for key in entries.keys():
            res.append(f"  {key}")
    res.append("")
    return res


def update_expected_js_docs():
    EXPECTED_DOCS_FILE.write_text("\n".join(check_list()))


def check_expected_js_docs():
    expected_lines = EXPECTED_DOCS_FILE.read_text().splitlines()
    new_lines = check_list()
    new_lines.pop()
    diffs = list(
        difflib.unified_diff(
            expected_lines,
            new_lines,
            fromfile="old expected_js_docs.txt",
            tofile="new expected_js_docs.txt",
        )
    )
    if not diffs:
        print("No changes")
        return 0
    print(
        "Set of documented APIs changed. If this is intended, run ./tools/check_documented_functions.py --update"
    )
    for l in diffs:
        print(l)
    return 1


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare the set of documented JS APIs to the expected set or update the expected set"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the set of documented JS APIs",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the expected set of documented JS APIs",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not (args.update ^ args.check):
        print("Expected exactly one of --check and --update")
        sys.exit(1)

    if args.update:
        update_expected_js_docs()
        sys.exit(0)

    if args.check:
        sys.exit(check_expected_js_docs())


if __name__ == "__main__":
    main()
