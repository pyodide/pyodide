#!/bin/bash

# get the absolute path of the root folder
ROOT=`cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 ; pwd -P`

# emsdk_env.sh is fairly noisy, and suppress error message if the file doesn't
# exist yet (i.e. before building emsdk)
source "$ROOT/emsdk/emsdk/emsdk_env.sh" 2> /dev/null || true
export PATH="$ROOT/node_modules/.bin/:$ROOT/emsdk/emsdk/ccache/git-emscripten_64bit/bin:$PATH:$ROOT/packages/.artifacts/bin/"
export EM_DIR=$(dirname $(which emcc.py || echo "."))
# This variable is set by emsdk activate, and is hashed by ccache. We set it to avoid ccache cache misses.
export EM_CONFIG="$ROOT/emsdk/emsdk/.emscripten"
