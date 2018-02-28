# Pyodide

This provides an integration layer when running an empscripten-compiled CPython
inside a web browser. It provides transparent conversion of objects between
Javascript and Python and a sharing of global namespaces. When inside a browser,
this means Python has full access to the Web APIs.

# Building

These instructions were tested on Linux. OSX should be substantively the same.

1. Build/install emscripten according to its instructions.

2. Enable the emscripten environment (`source emsdk_env.sh`)

3. Build this project.

   Type `make`.
