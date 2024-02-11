#!/usr/bin/env bash

# Do not keep running on errors
set -e

# https://pyodide.org/en/stable/development/new-packages.html#prerequisites
pip install -e ./pyodide-build

export PYODIDE_RECIPE_BUILD_DIR=/tmp/pyodide-build
mkdir -p "$PYODIDE_RECIPE_BUILD_DIR"
echo "export PYODIDE_RECIPE_BUILD_DIR=$PYODIDE_RECIPE_BUILD_DIR" >> ~/.bashrc
ln -sf "$PYODIDE_RECIPE_BUILD_DIR" packages/.build || echo "Note: Could not create convenience symlink packages/.build"

# Building emsdk and cpython takes a few minutes to run, so we do not run it here.
#
# make -C emsdk
# make -C cpython
