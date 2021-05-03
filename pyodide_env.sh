#!/bin/bash

ROOT=`dirname ${BASH_SOURCE[0]}`

# emsdk_env.sh is fairly noisy, and suppress error message if the file doesn't
# exist yet (i.e. before building emsdk)
source "$ROOT/emsdk/emsdk/emsdk_env.sh" 2> /dev/null || true
export PATH="$ROOT/node_modules/.bin/:$PATH:$ROOT/packages/.artifacts/bin/"
export EM_DIR=$(dirname $(which emcc.py || echo "."))
