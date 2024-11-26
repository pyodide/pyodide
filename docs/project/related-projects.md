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
- [react-py Playground](https://elilambnz.github.io/react-py/playground) uses Pyodide as part of the `react-py` package documentation. Try out code snippets and packages directly in your browser without logging in.
- [marimo](https://github.com/marimo-team/marimo) is a reactive notebook that is compatible with Pyodide with an [online editor](https://marimo.app/) that runs entirely in the browser. These notebooks can also run as standalone applications or embedded in blogs.
- [quarto-pyodide](https://github.com/coatless-quarto/pyodide) uses Pyodide
  to create interactive code cells and documents within a variety of
  [Quarto](https://quarto.org/) document formats like
  HTML Documents, RevealJS, Books, and Websites.
- [PyCafe](https://py.cafe) lets you host, edit, and share Python apps in your browser with a single click.
- [quarto-live](https://github.com/r-wasm/quarto-live) uses Pyodide
  to create interactive Python code cells and exercises in [Quarto](https://quarto.org/) documents.

## Workarounds for common WASM and browser limitations

- [pyodide-http](https://github.com/koenvo/pyodide-http) Provides patches for
  widely used http libraries to make them work in Pyodide environments like
  JupyterLite.

## Dashboards and visualization

- [WebDash](https://github.com/ibdafna/webdash) is a Plotly Dash distribution
  that runs entirely in the browser, using Pyodide.
- [Flet](https://flet.dev) is a UI framework for your Pyodide apps based on Flutter.
- [stlite](https://github.com/whitphx/stlite) is a serverless version of [Streamlit](https://streamlit.io/) running on Pyodide.
- [Gradio-Lite](https://www.gradio.app/guides/gradio-lite) is a serverless version of [Gradio](https://www.gradio.app/) running on Pyodide.

## Other projects

- [wc-code](https://github.com/vanillawc/wc-code) is a library to run
  JavaScript, Python, and Theme in the browser with inline code blocks.
  It uses Pyodide to execute Python code.
- [SymPy Beta](https://github.com/eagleoflqj/sympy_beta) is a fork of SymPy
  Gamma. It's an in-browser answer engine with a Pyodide backend.
- [react-py](https://github.com/elilambnz/react-py) is a library that allows for easy integration of Pyodide in React applications. It provides convenient hooks for running Python code.
- [inseri core](https://wordpress.org/plugins/inseri-core/) is a WordPress plugin that introduces scientific and interactive Gutenberg blocks to facilitate open science. The [Python Code block](https://docs.inseri.swiss/blocks/python/) allows to run Python code in the browser using Pyodide.
