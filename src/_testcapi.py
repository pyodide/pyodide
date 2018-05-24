"""
A shim to skip tests involving the _testcapi extension, since we don't build
it.
"""

import unittest

raise unittest.SkipTest("No _testcapi")
