#!/bin/sh
python2 emsdk/emsdk/emscripten/tag-1.38.4/tools/file_packager.py build/$1.data --preload $2 --js-output=build/$1.js --export-name=pyodide --exclude \*.wasm.pre --exclude __pycache__
uglifyjs build/$1.js -o build/$1.js
