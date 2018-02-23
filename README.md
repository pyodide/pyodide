# Calling Python from Javascript with value conversion

# Building

These instructions were tested on Linux. OSX should be substantively the same.

1. Build emscripten according to [these
   instructions](https://developer.mozilla.org/en-US/docs/WebAssembly/C_to_wasm).

2. Enable the emscripten environment (`source emsdk_env.sh`)

3. Build [cpython-emscripten](https://github.com/dgym/cpython-emscripten):

   1. Clone the git repository

   2. cd into `3.5.2`, and type `make`.

4. Build this project.

   [It assumes that `cpython-emscripten` was checked out and built in a
   directory alongside this project. TODO: Provide a way to specify the
   cpython-emscripten location]

   Type `make`.
