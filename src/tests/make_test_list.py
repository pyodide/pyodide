"""
Generate a list of test modules in the CPython distribution.
"""

import os
from pathlib import Path


TEST_DIR = (
    Path(__file__).parents[2] / "cpython/installs/python-3.9.5/lib/python3.9/test/"
)


explanation = """\
# This list is generated with test/make_test_list.py script, which needs
# to be re-run after each CPython update.
#
# Test modules with a failure reason after their name are either skipped
# or marked as a known failure in pytest.
#
# Following reason codes are skipped, as they lead to segfaults:
# - segfault-<syscall>: segfault in the corresponding system call.
#
# While the below reason codes are marked as a known failure. By default, they
# are also skipped. To run them, provide --run-xfail argument to pytest,
# - platform-specific: This is testing something about a particular platform
#   that isn't relevant here
# - async: relies on async
# - floating point: Failures caused by floating-point differences
# - threading: Failures due to lack of a threading implementation
# - subprocess: Failures caused by no subprocess module. Some of these are
#   because the underlying functionality depends on subprocess, and others are
#   just a side-effect of the way the test is written. The latter should
#   probably be marked as "skip" or rearchitected so we don't have to skip the
#   whole module.
# - networking: Fails because it tests low-level networking.
# - dbm: Failures due to no dbm module
# - strftime: Failures due to differences / shortcomings in WebAssembly's
#   implementation of date/time formatting in strftime and strptime
# - permissions: Issues with the test writing to the virtual filesystem
# - locale: Fails due to limitations in the included locale implementation.
# - multiprocessing: Fails due to no multiprocessing implementation.
# - fs: Fails due to virtual filesystem issues.
# - nonsense: This functionality doesn't make sense in this context. Includes
#   things like `pip`, `distutils`
# - crash: The Python interpreter just stopped without a traceback. Will require
#   further investigation. This usually seems to be caused by calling into a
#   system function that doesn't behave as one would expect.
# - crash-chrome: Same as crash but only affecting Chrome
# - crash-firefox: Same as crash but only affecting Firefox

"""


def collect_old_error_flags():
    old_error_flags = {}
    try:
        with open(Path(__file__).parent / "python_tests.txt") as fp:
            for line in fp:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                error_flags = line.split()
                name = error_flags.pop(0)
                if error_flags:
                    old_error_flags[name] = error_flags
    except FileNotFoundError:
        pass
    return old_error_flags


def collect_tests(base_dir):
    """Collect CPython unit tests"""
    # Note: this functionality is somewhat equivalent to pytest test
    # collection.
    tests = []

    for root, dirs, files in os.walk(base_dir):
        root = Path(root).relative_to(base_dir)

        if str(root) == ".":
            root = ""
        else:
            root = ".".join(str(root).split("/")) + "."

        for filename in files:
            filename = Path(filename)
            if str(filename).startswith("test_") and filename.suffix == ".py":
                tests.append(root + filename.stem)

    tests.sort()
    return tests


if __name__ == "__main__":
    old_error_flags = collect_old_error_flags()
    tests = collect_tests(TEST_DIR)
    with open("python_tests.txt", "w") as fp:
        fp.write(explanation)
        for test in tests:
            error_flags = " ".join(old_error_flags.get(test, []))
            line = test
            if error_flags:
                line += "    " + error_flags
            fp.write(line + "\n")
