"""
Generate a list of test modules in the CPython distribution.
"""

import os
from pathlib import Path
from sys import version
from typing import Any

import ruamel.yaml

yaml = ruamel.yaml.YAML()
PYODIDE_ROOT = Path(__file__).parents[2]
LIB_DIR = PYODIDE_ROOT / "cpython/build" f"/Python-{version.split(' ')[0]}" f"/Lib/"

PYTHON_TESTS_YAML = Path(__file__).parent / "python_tests.yaml"


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
    for idx, test in reversed(list(enumerate(doc_group))):
        if get_test_name(test) not in tests:
            print("removing", test)
            del doc_group[idx]

    for idx, test in enumerate(sorted(tests)):
        if idx == len(doc_group) or get_test_name(doc_group[idx]) != test:
            print("adding", test)
            doc_group.insert(idx, test)


if __name__ == "__main__":
    doc = get_old_yaml()
    update_tests(doc, collect_tests(LIB_DIR / "test"))

    yaml.dump(doc, PYTHON_TESTS_YAML)
