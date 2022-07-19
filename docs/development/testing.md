(testing)=

# Testing and benchmarking

## Testing

### Running the Python test suite

You can use either Selenium or Playwright to run the pytest suite of tests.

Install the following dependencies into the default Python installation:

```bash
pip install pytest pytest-instafail pytest-httpserver
```

There are 3 test locations that are collected by pytest,

- `src/tests/`: general Pyodide tests and tests running the CPython test suite
- `pyodide-build/pyodide_build/tests/`: tests related to Pyodide build system
  (do not require selenium or playwright to run)
- `packages/*/test_*`: package specific tests.

#### Selenium (default)

```
pip install selenium
```

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) and
[chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads)
and check that they are in your `PATH`.

### Running the Python test suite

To run the test suite, run `pytest` from the root directory of Pyodide:

```bash
pytest
```

You can run the tests from a specific file with:

```bash
pytest path/to/test/file.py
```

To speed things up you may wish to filter out two of the browsers. Node runs
tests the fastest so:

```bash
pytest -k "not chrome and not fire"
```

is often helpful. Some browsers sometimes produce informative errors than others
so if you are getting confusing errors it is worth rerunning the test on each
browser. If you are still confused, try {ref}`manual-testing` which is more
flexible.

There are 5 test locations that are collected by pytest:

- `src/tests/`: general Pyodide tests and tests running the CPython test suite
  system.
- `pyodide-build/pyodide_build/tests/`: tests related to Pyodide build system
  (do not require selenium to run)
- `packages/test_common.py`: common tests for packages.
- `packages/*/test_*`: package specific tests.

#### Running tests with Playwright

By default, the tests will be run with Selenium. It is possible to run tests
with playwright instead as follows.

First install playwright

```bash
pip install playwright && python -m playwright install
```

Then use the `--runner` argument to specify to run tests with playwright.

```bash
pytest --runner playwright
```

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

Python is linted with `flake8`, `black` and `mypy`.
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

## Testing framework

(run-in-pyodide)=

### run_in_pyodide

Many tests simply involve running a chunk of code in Pyodide and ensuring it
doesn't error. In this case, one can use the `run_in_pyodide` decorate from
`pytest_pyodide.decorator`, e.g.

```python
from pytest_pyodide import run_in_pyodide

@run_in_pyodide
def test_add(selenium):
    assert 1 + 1 == 2
```

In this case, the body of the function will automatically be run in Pyodide. The
decorator can also be called with a `packages` argument to load packages before
running the test. For example:

```python
from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages = ["regex"])
def test_regex(selenium_standalone):
    import regex
    assert regex.search("o", "foo").end() == 2
```

If your `run_in_pyodide` test is failing, it will generate much better error
messages if the packages `pytest` and `tblib` are available in Pyodide, so it is
recommended that you build them:

```sh
PYODIDE_PACKAGES="pytest, tblib, whatever-else" make -C packages
```

If you need to xfail your test on a certain browser, you can use
`pytest.mark.xfail_browsers`. You can also use `@run_in_pyodide` with
`pytest.mark.parametrize`, with `hypothesis`, etc. `@run_in_pyodide` MUST be the
innermost decorator. Any decorators inside of `@run_in_pyodide` will be have no
effect on the behavior of the test.

```python
from pytest_pyodide import run_in_pyodide

@pytest.mark.parametrize("x", [1, 2, 3])
@run_in_pyodide(packages = ["regex"])
def test_type_of_int(selenium, x):
    assert type(x) is int
```

These arguments must be picklable. You can also use fixtures as long as the
return values of the fixtures are picklable (most commonly, if they are `None`).
As a special case, the function will see the `selenium` fixture as `None` inside
the test.

It is possible to use `run_in_pyodide` as an inner function:

```py
def test_inner_function(selenium):
    @run_in_pyodide
    def inner_function(selenium, x):
        assert x == 6
        return 7

    assert inner_function(selenium_mock, 6) == 7
```

Again both the arguments and return value must be pickleable.

Also, the function will not see closure variables at all:

```py
def test_inner_function_closure(selenium):
    x = 6
    @run_in_pyodide
    def inner_function(selenium):
        assert x == 6
        return 7

    # Raises `NameError: 'x' is not defined`
    assert inner_function(selenium_mock) == 7
```

### Custom test marks

We support four test marks:

`@pytest.mark.skip_refcount_check` and `pytest.mark.skip_pyproxy_check` disable
respectively the check for JavaScript references and the check for PyProxies.
If a test creates JavaScript references or PyProxies and does not clean them up,
by default the tests will fail. If a test is known to leak objects, it is
possible to disable these checks with these markers.

`pytest.mark.driver_timeout(timeout)`: Set script timeout in WebDriver. If the
test is known to take a long time, you can extend the deadline with this marker.

`pytest.mark.xfail_browsers(chrome="why chrome fails")`: xfail a test in
specific browsers.
