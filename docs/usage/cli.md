# The Pyodide Python CLI

Pyodide includes a python CLI command which is a drop in replacement for the
native python CLI. For example all the following should work as expected:
```sh
python -c "some command"
python file.py
python -m some.module
```
This is primarily useful for testing and experimentation. It can also be helpful
to install Pyodide Python packages using uv or pip for bundling purposes.

Execution is not sandboxed, this Pyodide Python has direct access to the native
file system.

## Platform support

It should work on Linux and macOS. There is currently no Windows support. It
requires an installation of NodeJS >= 20.

## Installation

There are three ways to install the Pyodide CLI. 


### Github releases

You can download `pyodide-core-0.vv.vv.tar.bz2` from github releases and
extract it. It contains the `python` command inside.

### Pyodide venv

You can install `pyodide-build` with pip or uv and then run `pyodide venv .venv-pyodide`.
If you use uv to install `pyodide-build` make sure you run `uv pip install pip`, it will
not work without pip installed.

### uv

You can use `uv python install cpython-3.13.2-emscripten-wasm32-musl` to install
Pyodide. Then you can create a Pyodide venv with
```sh 
uv venv .venv-pyodide -p cpython-3.13.2-emscripten-wasm32-musl
```
When you install packages you should use:
```sh
uv pip install --no-build --extra-index-url https://index.pyodide.org/0.28.3/ --index-strategy unsafe-best-match 
```

You can set these settings by default by putting the following in `uv.toml`:
```toml
no-build = true
index-strategy = "unsafe-best-match"

[[index]]
url = "https://index.pyodide.org/0.28.3/"
```
Or the following in `pyproject.toml`
```toml
tool.uv.no-build = true
tool.uv.index-strategy = "unsafe-best-match"

[[tool.uv.index]]
url = "https://index.pyodide.org/0.28.3/"
```
But you may not want to apply any of these settings to your native Python
virtual environment.
