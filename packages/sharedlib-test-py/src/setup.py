#!/usr/bin/env python

from setuptools import Extension, setup


setup(
    name="sharedlib-test-py",
    version="1.0",
    description="A package to test Pyodide shared libraries",
    author="Pyodide team",
    url="https://github.com/pyodide/pyodide",
    ext_modules=[Extension("sharedlib_test", ["sharedlib-test.c"])],
)
