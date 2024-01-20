# Do not keep running on errors
set -e

# https://pyodide.org/en/stable/development/new-packages.html#prerequisites
pip install -e ./pyodide-build
make -C emsdk
make -C cpython
