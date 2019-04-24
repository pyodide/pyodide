#!/usr/bin/env python

from distutils.core import setup

setup(
    name='micropip',
    version='0.1',
    description='A small version of pip for running in pyodide',
    author='Michael Droettboom',
    author_email='mdroettboom@mozilla.com',
    url='https://github.com/iodide-project/pyodide',
    py_modules=['micropip'],
)
