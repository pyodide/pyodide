(pyodide-cli)=

# pyodide CLI

This page documents the Pyodide Command Line Interface (CLI) interface. In addition to the commands defined by `pyodide-build`, documented below, other subcommands are defined in external packages (which can be installed with pip):

- `pyodide pack`, defined in [pyodide-pack](https://github.com/pyodide/pyodide-pack) is a package bundler for Pyodide

```{eval-rst}
.. click:: pyodide_cli.app:click_object
   :prog: pyodide
   :nested: full
```
