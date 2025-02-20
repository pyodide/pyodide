(adding-packages-into-pyodide-distribution)=

# Adding Packages into Pyodide Distribution

You can build your package through the tools we provide and run it on Pyodide.
However, as of 2025/01, PyPI does not support Emscripten/wasm32 wheels, so it is not
easy to distribute your package to Pyodide users.
Therefore, to make your package available to all Pyodide users, it is recommended to
add it to the Pyodide distribution, so that the package can be distributed with
Pyodide runtime.

## Adding a package

To add a package to the Pyodide distribution,
you need to write a recipe (see {ref}`building-packages-using-recipe`),
and add the recipe in the [`pyodide-recipes`](https://github.com/pyodide/pyodide-recipes) repository.

### Writing tests for your package

To ensure that your package works correctly in Pyodide,
you should write tests for your package.

The tests should go in one or more files like
`packages/<package-name>/test_xxx.py`. Most packages have one test file named
`test_<package-name>.py`. The tests should look like:

```py
from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["<package-name>"])
def test_mytestname(selenium):
  import <package-name>
  assert package.do_something() == 5
  # ...
```

For more info on `run_in_pyodide` see
[pytest-pyodide](https://github.com/pyodide/pytest-pyodide).

If you want to run your package's full pytest test suite and your package
vendors tests you can do it like:

```py
from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["<package-name>-tests", "pytest"])
def test_mytestname(selenium):
  import pytest
  assert pytest.main(["--pyargs", "<package-name>", "-k", "some_filter", ...]) == 0
```

you can put whatever command line arguments you would pass to `pytest` as
separate entries in the list.

```{note}
As pyodide-recipes repository contains more than 250 packages in total,
It is highly discouraged to run the full test suite of your package.

If you want to run your package's full pytest test suite,
it is recommended to run the full test suite in your local repository,
while running a very simple unit tests in the pyodide-recipes repository.
```

### Adding a "big" package

If your package takes a very long time (more than 10 minutes) to build,
you should consider building the package in a separate repository and
only adding the built wheel to the `pyodide-recipes` repository.

A good example of this is [PyArrow](https://github.com/pyodide/pyodide-recipes/blob/main/packages/pyarrow/meta.yaml).
PyArrow takes more than 30 minutes to build, so building it in the `pyodide-recipes`
repository would slow down the CI process significantly.

Therefore, it is built in a separate repository and the built wheel is added in the
recipe file, without building the package from source.
