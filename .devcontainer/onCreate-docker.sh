#!/usr/bin/env bash

# Do not keep running on errors
set -e

# https://pyodide.org/en/stable/development/new-packages.html#prerequisites
pip install -e ./pyodide-build

echo "export PYODIDE_RECIPE_BUILD_DIR=/tmp/pyodide-build" >> ~/.bashrc

# Building emsdk and cpython takes a few minutes to run, so we do not run it here.
#
# make -C emsdk
# make -C cpython
