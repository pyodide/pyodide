# [Pyodide](https://github.com/iodide-project/pyodide)


[![Build Status](https://circleci.com/gh/iodide-project/pyodide.png)](https://circleci.com/gh/iodide-project/pyodide)
[![Documentation Status](https://readthedocs.org/projects/pyodide/badge/?version=latest)](https://pyodide.readthedocs.io/?badge=latest)

The Python scientific stack, compiled to WebAssembly.

## What is Pyodide?

**Pyodide** brings the Python runtime to the browser via WebAssembly, along with the Python scientific stack including NumPy, Pandas, Matplotlib, parts of SciPy, and NetworkX. The [`packages` directory](https://github.com/iodide-project/pyodide/tree/master/packages) lists over 35 packages which are currently available.

**Pyodide** provides transparent conversion of objects between Javascript and Python.
When used inside a browser, Python has full access to the Web APIs.

While closely related to the [iodide project](https://iodide.io), a tool for *literate scientific computing and communication for the web*, Pyodide goes beyond running in a notebook environment. To maximize the flexibility of the modern web, **Pyodide** may
be used standalone in any context where you want to **run Python inside a web
browser**.

## Try Pyodide (no installation needed)

Try the [iodide demo notebook](https://alpha.iodide.io/notebooks/300/) or fire
up a [Python REPL](https://pyodide-cdn2.iodide.io/latest/full/console.html) directly in your
browser.

For further information, look through the [documentation](https://pyodide.readthedocs.io/).

## Getting Started

Pyodide offers three different ways to get started depending on your needs and technical resources.
These include:

- Use hosted distribution of pyodide: see [using pyodide from
  Javascript](https://pyodide.readthedocs.io/en/latest/using_pyodide_from_javascript.html)
  documentation.
- Download a pre-built version from this
  repository's [releases
  page](https://github.com/iodide-project/pyodide/releases/) and serve its contents with
  a web server.
- [Build Pyodide from source](https://pyodide.readthedocs.io/en/latest/building_from_sources.html)
  - Build natively with `make`: primarily for Linux users who want to
    experiment or contribute back to the project.
  - [Use a Docker image](https://pyodide.readthedocs.io/en/latest/building_from_sources.html#using-docker):
    recommended for Windows and macOS users and for Linux users who prefer a
    Debian-based Docker image with the dependencies already installed.

## Contributing

Please view the
[contributing guide](https://pyodide.readthedocs.io/en/latest/rootdir.html#how-to-contribute)
for tips on filing issues, making changes, and submitting pull requests.

## License

Pyodide uses the Mozilla Public License Version 2.0. See the
[LICENSE file](LICENSE) for more details.
