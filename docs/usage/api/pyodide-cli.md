(pyodide-cli)=

# pyodide CLI

This page documents the Pyodide Command Line Interface (CLI) interface. In addition, the the commands defined by `pyodude-build`, documented below, other subcommands are defined in external packages (which can be installed with pip):

- `pyodide audit`, defined in [auditwheel-emscripten](https://github.com/ryanking13/auditwheel-emscripten), provides auditwheel-like tools for Pyodide
- `pyodide pack`, defined in [pyodide-pack](https://github.com/pyodide/pyodide-pack) is a package bundler for Pyodide

```{eval-rst}
.. click:: pyodide_cli.app:typer_click_object
   :prog: pyodide
   :nested: full
```
