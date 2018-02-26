# Pyodide

This provides an integration layer when running an empscripten-compiled CPython
inside a web browser. It provides transparent conversion of objects between
Javascript and Python and a sharing of global namespaces. When inside a browser,
this means Python has full access to the Web APIs.

# Building

These instructions were tested on Linux. OSX should be substantively the same.

1. Build emscripten according to [these
   instructions](https://developer.mozilla.org/en-US/docs/WebAssembly/C_to_wasm).

2. Enable the emscripten environment (`source emsdk_env.sh`)

3. Build [cpython-emscripten](https://github.com/dgym/cpython-emscripten)

   In order to get Python 3.6.4 support, you need to use the py3.6 branch on
   mdboom's fork.

   ```
   git clone https://github.com/mdboom/cpython-emscripten.git
   cd cpython-emscripten
   git checkout py3.6
   cd 3.6.4
   make
   ```

4. Build this project.

   [It assumes that `cpython-emscripten` was checked out and built in a
   directory alongside this project. TODO: Provide a way to specify the
   cpython-emscripten location]

   Type `make`.
