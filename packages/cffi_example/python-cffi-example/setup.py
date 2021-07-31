#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages

os.chdir(os.path.dirname(sys.argv[0]) or ".")

setup(
    name="cffi-example",
    version="0.1",
    description="An example project using Python's CFFI",
    long_description=open("README.rst", "rt").read(),
    url="https://github.com/wolever/python-cffi-example",
    author="David Wolever",
    author_email="david@wolever.net",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: Implementation :: PyPy",
        "License :: OSI Approved :: BSD License",
    ],
    packages=find_packages(),
    install_requires=["cffi>=1.0.0"],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=[
        "./cffi_example/build_person.py:ffi",
        "./cffi_example/build_fnmatch.py:ffi",
    ],
)
