#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="micropip",
    version="0.1",
    description="A small version of pip for running in pyodide",
    author="Michael Droettboom",
    author_email="mdroettboom@mozilla.com",
    url="https://github.com/pyodide/pyodide",
    packages=find_packages(
        where=".",
    ),
)
