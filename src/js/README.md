# js/pyodide

The Javascript code in this folder is responsible for the following tasks:

1. Defines the public Javascript API
   - Package loading code to allow loading of other Python packages.
   - Can load micropip.py to bootstrap loading of pure Python wheels
2. Loads the CPython interpreter and the core/pyodide emscripten application
   which embeds the interpreter.
3. Injects the js/pyodide Javascript API into sys.modules. This is the final
   runtime dependency for core/pyodide & py/pyodide, so after this step the
   interpreter is fully up and running.
