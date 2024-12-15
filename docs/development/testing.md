(testing)=

# Testing and benchmarking

## Testing

### Running the Python test suite

1. Install the following dependencies into the default Python installation:

```bash
pip install pytest-pyodide pytest-httpserver
```

`pytest-pyodide` is a pytest plugin for testing Pyodide
and third-party applications that use Pyodide.

> See: [pytest-pyodide](https://github.com/pyodide/pytest-pyodide) for more information.

2. Install [geckodriver](https://github.com/mozilla/geckodriver/releases) or
   [chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
   and check that they are in your `PATH`.

3. To run the test suite, run `pytest` from the root directory of Pyodide:

```bash
pytest
```

There are 2 test locations that are collected by pytest,

- `src/tests/`: general Pyodide tests and tests running the CPython test suite
- `packages/*/test_*`: package specific tests.

You can run the tests from a specific file with:

```bash
pytest path/to/test/file.py
```

Some browsers sometimes produce informative errors than others
so if you are getting confusing errors it is worth rerunning the test on each
browser. You can use `--runtime` commandline option to specify the browser runtime.

```bash
pytest --runtime firefox
pytest --runtime chrome
pytest --runtime node
```

#### Custom test marks

We support custom test marks:

`@pytest.mark.skip_refcount_check` and `pytest.mark.skip_pyproxy_check` disable
respectively the check for JavaScript references and the check for PyProxies.
If a test creates JavaScript references or PyProxies and does not clean them up,
by default the tests will fail. If a test is known to leak objects, it is
possible to disable these checks with these markers.

### Running the JavaScript test suite

To run tests on the JavaScript Pyodide package using Mocha, run the following
commands,

```sh
cd src/js
npm test
```

To check TypeScript type definitions run,

```sh
npx tsd
```

(manual-testing)=

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

We lint with `pre-commit`.

Python is linted with `ruff`, `black` and `mypy`.
JavaScript, markdown, yaml, and html are linted with `prettier`.
C is linted with `clang-format`.

To lint the code, run:

```bash
pre-commit run -a
```

You can have the linter automatically run whenever you commit by running

```bash
pip install pre-commit
pre-commit install
```

and this can later be disabled with

```bash
pre-commit uninstall
```

If you don't lint your code, certain lint errors will be fixed automatically by
`pre-commit.ci` which will push fixes to your branch. If you want to push more
commits, you will either have to pull in the remote changes or force push.
