"""
Generate a list of test modules in the CPython distribution.
"""

import os
from pathlib import Path


TEST_DIR = (Path(__file__).parent
            / "cpython/build/3.7.4/host/lib/python3.7/test")


def collect_tests(base_dir):
    """Collect CPython unit tests"""
    # Note: this functionality is somewhat equivalent to pytest test
    # collection.
    tests = []

    for root, dirs, files in os.walk(base_dir):
        root = Path(root).relative_to(base_dir)

        if str(root) == '.':
            root = ''
        else:
            root = '.'.join(str(root).split('/')) + '.'

        for filename in files:
            filename = Path(filename)
            if str(filename).startswith("test_") and filename.suffix == ".py":
                tests.append(root + filename.stem)

    tests.sort()
    return tests


if __name__ == '__main__':
    tests = collect_tests(TEST_DIR)
    with open("python_tests.txt", "w") as fp:
        for test in tests:
            fp.write(test + '\n')
