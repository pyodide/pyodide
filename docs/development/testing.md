(testing)=

# Testing and benchmarking

## Testing

### Requirements

Install the following dependencies into the default Python installation:

```bash
pip install pytest selenium pytest-instafail pytest-httpserver
```

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) and
[chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
and check that they are in your `PATH`.

### Running the Python test suite

To run the pytest suite of tests, from the root directory of Pyodide, type on the command line:

```bash
pytest
```

There are 3 test locations that are collected by pytest,

- `src/tests/`: general Pyodide tests and tests running the CPython test suite
- `pyodide-build/pyodide_build/tests/`: tests related to Pyodide build system
  (do not require selenium to run)
- `packages/*/test_*`: package specific tests.

### Running the JavaScript test suite

To run tests on the JavaScript Pyodide package using Mocha, run the following commands,

```sh
cd src/js
npm test
```

To check TypeScript type definitions run,

```sh
npx tsd
```

### Manual interactive testing

To run tests manually:

1. Build Pyodide, perhaps in the docker image

2. From outside of the docker image, `cd` into the `dist` directory and run
   `python -m http.server`.

3. Once the webserver is running, simple interactive testing can be run by
   visiting the URL: `http://localhost:<PORT>/console.html`. It's recommended to
   use `pyodide.runPython` in the browser console rather than using the repl.

## Benchmarking

To run common benchmarks to understand Pyodide's performance, begin by
installing the same prerequisites as for testing. Then run:

```bash
PYODIDE_PACKAGES="numpy,matplotlib" make benchmark
```

## Linting

Python is linted with `flake8`, `black` and `mypy`.
JavaScript is linted with `prettier`.
C is linted with `clang-format`.

To lint the code, run:

```bash
make lint
```

## Testing framework

### run_in_pyodide

Many tests simply involve running a chunk of code in Pyodide and ensuring it
doesn't error. In this case, one can use the `run_in_pyodide` decorate from
`pyodide_test_runner.decorator`, e.g.

```python
from pyodide_test_runner import run_in_pyodide

@run_in_pyodide
def test_add():
    assert 1 + 1 == 2
```

In this case, the body of the function will automatically be run in Pyodide.
The decorator can also be called with arguments. It has two configuration
options --- standalone and packages.

Setting `standalone = True` starts a standalone browser session to run the test
(the session is shared between tests by default). This is useful for testing
things like package loading.

The `packages` option lists packages to load before running the test. For
example,

```python
from pyodide_test_runner import run_in_pyodide

@run_in_pyodide(standalone = True, packages = ["regex"])
def test_regex():
    import regex
    assert regex.search("o", "foo").end() == 2
```
