"""
Generate a list of test modules in the CPython distribution.
"""

import os

import ruamel.yaml

yaml = ruamel.yaml.YAML()

from pathlib import Path
from sys import version_info

PYODIDE_ROOT = Path(__file__).parents[2]
LIB_DIR = (
    PYODIDE_ROOT / "cpython/installs"
    f"/python-{version_info.major}.{version_info.minor}.{version_info.micro}"
    f"/lib/python{version_info.major}.{version_info.minor}"
)

PYTHON_TESTS_YAML = Path(__file__).parent / "python_tests.yaml"

explanation = """\
This list is generated with test/make_test_list.py script, which needs
to be re-run after each CPython update.

Test modules with a failure reason after their name are either skipped
or marked as a known failure in pytest.

Following reason codes are skipped, as they lead to segfaults:
- segfault-<syscall>: segfault in the corresponding system call.

While the below reason codes are marked as a known failure. By default, they
are also skipped. To run them, provide --run-xfail argument to pytest,
- platform-specific: This is testing something about a particular platform
  that isn't relevant here
- async: relies on async
- floating point: Failures caused by floating-point differences
- threading: Failures due to lack of a threading implementation
- subprocess: Failures caused by no subprocess module. Some of these are
  because the underlying functionality depends on subprocess, and others are
  just a side-effect of the way the test is written. The latter should
  probably be marked as "skip" or rearchitected so we don't have to skip the
  whole module.
- networking: Fails because it tests low-level networking.
- dbm: Failures due to no dbm module
- strftime: Failures due to differences / shortcomings in WebAssembly's
  implementation of date/time formatting in strftime and strptime
- permissions: Issues with the test writing to the virtual filesystem
- locale: Fails due to limitations in the included locale implementation.
- multiprocessing: Fails due to no multiprocessing implementation.
- fs: Fails due to virtual filesystem issues.
- nonsense: This functionality doesn't make sense in this context. Includes
  things like `pip`, `distutils`
- crash: The Python interpreter just stopped without a traceback. Will require
  further investigation. This usually seems to be caused by calling into a
  system function that doesn't behave as one would expect.
- crash-chrome: Same as crash but only affecting Chrome
- crash-firefox: Same as crash but only affecting Firefox
"""


def get_old_yaml():
    try:
        with open(PYTHON_TESTS_YAML) as fp:
            result = yaml.load(fp)
    except FileNotFoundError:
        result = yaml.seq()
    result.yaml_set_start_comment(explanation)
    return result


def collect_tests(base_dir: Path) -> set:
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


def get_test_name(test) -> str:
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
