"""
Generate a list of test modules in the CPython distribution.
"""

import os

tests = []

TEST_DIR = "../cpython/build/3.6.4/host/lib/python3.6/test"
for root, dirs, files in os.walk(
        "../cpython/build/3.6.4/host/lib/python3.6/test"):
    root = os.path.relpath(root, TEST_DIR)
    if root == '.':
        root = ''
    else:
        root = '.'.join(root.split('/')) + '.'

    for filename in files:
        if filename.startswith("test_") and filename.endswith(".py"):
            tests.append(root + os.path.splitext(filename)[0])

tests.sort()
with open("python_tests.txt", "w") as fp:
    for test in tests:
        fp.write(test + '\n')
