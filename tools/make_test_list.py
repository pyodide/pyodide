#!/usr/bin/env python3

"""
Generate a list of test modules in the CPython distribution.
"""

import os
from pathlib import Path
from typing import Any

import ruamel.yaml
from common import PYODIDE_ROOT, get_makefile_envs

yaml = ruamel.yaml.YAML()
PYTHON_TESTS_YAML = PYODIDE_ROOT / "src/tests/python_tests.yaml"


def get_old_yaml():
    try:
        with open(PYTHON_TESTS_YAML) as fp:
            result = yaml.load(fp)
    except FileNotFoundError:
        result = yaml.seq()
    return result


def collect_tests(base_dir: Path) -> set[str]:
    """Collect CPython unit tests"""
    # Note: this functionality is somewhat equivalent to pytest test
    # collection.
    tests = set()

    for root, _, files in os.walk(base_dir):
        root = str(Path(root).relative_to(base_dir))

        if root == ".":
            root = ""
        else:
            root = ".".join(root.split("/")) + "."

        for filename in files:
            p = Path(filename)
            if filename.startswith("test_") and p.suffix == ".py":
                tests.add(root + p.stem)

    return tests


def get_test_name(test: str | dict[str, Any]) -> str:
    if isinstance(test, dict):
        name = next(iter(test.keys()))
    else:
        name = test
    return name


def update_tests(doc_group, tests):
    """Rewrite ``doc_group`` in place so it contains exactly ``tests``, sorted.

    Existing entries are matched by name so that any annotations attached to
    them are preserved. Tests that no longer exist are dropped and newly
    discovered tests are added as bare entries.
    """
    # Map each existing entry name to its item, preferring an annotated entry
    # over a bare one if the same name appears more than once. This also
    # de-duplicates entries.
    existing: dict[str, Any] = {}
    for item in doc_group:
        name = get_test_name(item)
        if name not in existing or isinstance(item, dict):
            existing[name] = item

    for name in existing:
        if name not in tests:
            print("removing", name)

    new_items = []
    for name in sorted(tests):
        if name in existing:
            new_items.append(existing[name])
        else:
            print("adding", name)
            new_items.append(name)

    # Mutate in place so any file-level comments attached to the sequence are
    # preserved by the round-trip dumper.
    doc_group[:] = new_items


if __name__ == "__main__":
    doc = get_old_yaml()
    version = get_makefile_envs()["PYVERSION"]
    LIB_DIR = PYODIDE_ROOT / f"cpython/build/Python-{version}/Lib/"
    update_tests(doc, collect_tests(LIB_DIR / "test"))

    yaml.dump(doc, PYTHON_TESTS_YAML)
