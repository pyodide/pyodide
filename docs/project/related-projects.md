# Related Projects

## WebAssembly ecosystem

- [emscripten](https://emscripten.org/) is the compiler toolchain for WebAssembly
  that made Pyodide possible.

## Notebook environments, IDEs, and REPLs

- [Iodide](https://github.com/iodide-project/iodide) is a notebook-like
  environment for literate scientific computing and communication for the
  web. It is no longer actively maintained. Historically, Pyodide started
  as plugin for iodide.
- [Starboard notebook](https://github.com/gzuidhof/starboard-notebook) is an
  in-browser literal notebook runtime that uses Pyodide for Python.
- [Basthon notebook](https://notebook.basthon.fr/) is a static fork of Jupyter
  notebook with a Pyodide kernel (currently in French).
- [JupyterLite](https://github.com/jupyterlite/jupyterlite) is a JupyterLab
  distribution that runs entirely in the browser, based on Pyodide.
- [futurecoder](https://futurecoder.io/) is an interactive Python
  course running on Pyodide. It includes an
  [IDE](https://futurecoder.io/course/#ide) with a REPL,
  debuggers, and automatic installation of
  any imported packages supported by Pyodide's `micropip`.

## Workarounds for common WASM and browser limitations

- [pyodide-http](https://github.com/koenvo/pyodide-http) Provides patches for
  widely used http libraries to make them work in Pyodide environments like
  JupyterLite.

## Dashboards and visualization

- [WebDash](https://github.com/ibdafna/webdash) is a Plotly Dash distribution
  that runs entirely in the browser, using Pyodide.

## Other projects

- [wc-code](https://github.com/vanillawc/wc-code) is a library to run
  JavaScript, Python, and Theme in the browser with inline code blocks.
  It uses Pyodide to execute Python code.
- [SymPy Beta](https://github.com/eagleoflqj/sympy_beta) is a fork of SymPy
  Gamma. It's an in-browser answer engine with a Pyodide backend.
