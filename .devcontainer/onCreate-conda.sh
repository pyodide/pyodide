#!/usr/bin/env bash

# Do not keep running on errors
set -ex

# from https://pyodide.org/en/stable/development/building-from-sources.html#using-make:
# - build-essential
# we install file because it is used by packages/ppl during configure
# we install gfortran because it is required by packages/scipy
# we install pkg-config with apt because it is commented out in environment.yml
sudo apt-get update && sudo apt-get install --yes build-essential file gfortran pkg-config

conda env create -n pyodide-env -f environment.yml
conda init bash
echo "conda activate pyodide-env" >> ~/.bashrc

# conda run -n pyodide-env make -C emsdk clean
# conda run -n pyodide-env make -C cpython clean

# https://pyodide.org/en/stable/development/building-from-sources.html#using-docker
export EMSDK_NUM_CORE=12 EMCC_CORES=12 PYODIDE_JOBS=12
echo "export EMSDK_NUM_CORE=12 EMCC_CORES=12 PYODIDE_JOBS=12" >> ~/.bashrc

export PYODIDE_RECIPE_BUILD_DIR=/tmp/pyodide-build
mkdir -p "$PYODIDE_RECIPE_BUILD_DIR"
echo "export PYODIDE_RECIPE_BUILD_DIR=$PYODIDE_RECIPE_BUILD_DIR" >> ~/.bashrc
ln -sf "$PYODIDE_RECIPE_BUILD_DIR" packages/.build || echo "Note: Could not create convenience symlink packages/.build"

conda run -n pyodide-env --live-stream pip install -r requirements.txt

# https://pyodide.org/en/stable/development/new-packages.html#prerequisites
conda run -n pyodide-env --live-stream pip install -e ./pyodide-build

# Building emsdk and cpython takes a few minutes to run, so we do not run it here.
#
# conda run -n pyodide-env --live-stream make -C emsdk
# conda run -n pyodide-env --live-stream make -C cpython
