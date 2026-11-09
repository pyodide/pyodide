#!/usr/bin/env python

from setuptools import Extension, setup

setup(
    name="test-sqlite3-extension",
    version="1.0",
    description="A package to test loading SQLite extensions in Pyodide",
    author="Pyodide team",
    url="https://github.com/pyodide/pyodide",
    packages=["sqlite3_extension_test"],
    # This is a SQLite extension, not a Python extension module. We build it
    # with setuptools so that it is shipped in the wheel like extensions on PyPI
    # such as sqlite-vec.
    ext_modules=[
        Extension(
            "sqlite3_extension_test._sqlite_ext", ["sqlite3_extension_test/ext.c"]
        )
    ],
)
