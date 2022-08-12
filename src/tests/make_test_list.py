"""
Generate a list of test modules in the CPython distribution.
"""

import os

import ruamel.yaml

yaml = ruamel.yaml.YAML()

from pathlib import Path
from sys import version_info
from typing import Any

PYODIDE_ROOT = Path(__file__).parents[2]
LIB_DIR = (
    PYODIDE_ROOT / "cpython/installs"
    f"/python-{version_info.major}.{version_info.minor}.{version_info.micro}"
    f"/lib/python{version_info.major}.{version_info.minor}"
)

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

    for root, _dirs, files in os.walk(base_dir):
        root = str(Path(root).relative_to(base_dir))

        if str(root) == ".":
            root = ""
        else:
            root = ".".join(str(root).split("/")) + "."

        for filename in files:
            p = Path(filename)
            if filename.startswith("test_") and p.suffix == ".py":
                tests.add(root + p.stem)

    return tests


def get_test_name(test: Any) -> str:
    if isinstance(test, dict):
        name = next(iter(test.keys()))
    else:
        name = test
    return name


def update_tests(doc_group, tests):
    for idx, test in enumerate(list(doc_group)):
        if get_test_name(test) not in tests:
            del doc_group[idx]

    for idx, test in enumerate(sorted(tests)):
        if idx == len(doc_group) or get_test_name(doc_group[idx]) != test:
            doc_group.insert(idx, test)


if __name__ == "__main__":
    doc = get_old_yaml()
    update_tests(doc, collect_tests(LIB_DIR / "test"))

    yaml.dump(doc, PYTHON_TESTS_YAML)
