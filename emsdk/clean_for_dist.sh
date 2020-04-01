#!/bin/sh
set -e
find . -name "*.o" -type f -delete
find . -name "*.a" -type f -delete
find -type d -name .git -prune -exec rm -rf {} \;
find -type d -name CMakeFiles -prune -exec rm -rf {} \;
rm -rf emsdk/emscripten/incoming/tests
rm -rf emsdk/emsdk/fastcomp-clang/fastcomp/src
rm -rf emsdk/zips
rm -rf emsdk/binaryen/master/test
rm -rf emsdk/.emscripten_cache
rm emsdk/.emscripten_cache.lock
rm emsdk/.emscripten_sanity
