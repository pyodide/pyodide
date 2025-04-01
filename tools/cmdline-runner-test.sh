#!/bin/bash
set -x
export PYODIDE_ROOT=$(pwd)
echo $PYODIDE_ROOT
source pyodide_env.sh
make pyodide_build
rm -rf test-cmdline-runner
mkdir test-cmdline-runner
cd test-cmdline-runner
git clone https://github.com/python-attrs/attrs --depth 1 --branch 25.3.0

python -m venv .venv-host
source .venv-host/bin/activate

pyodide venv .venv-pyodide
source .venv-pyodide/bin/activate
touch .venv-pyodide/lib/python3.13/site-packages/pty.py

cd attrs
pip install .[tests]
.venv-pyodide/bin/pip uninstall pytest_mypy_plugins
python -m pytest -k 'not mypy'
