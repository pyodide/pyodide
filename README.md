<div align="center">
  <a href="https://github.com/pyodide/pyodide">
  <img src="./docs/_static/img/pyodide-logo-readme.png" alt="Pyodide">
  </a>
</div>


[![Build Status](https://circleci.com/gh/pyodide/pyodide.png)](https://circleci.com/gh/pyodide/pyodide)
[![Documentation Status](https://readthedocs.org/projects/pyodide/badge/?version=latest)](https://pyodide.readthedocs.io/?badge=latest)

Python with the scientific stack, compiled to WebAssembly.

## What is Pyodide?

**Pyodide** brings the Python 3.8 runtime to the browser via WebAssembly, along
with the Python scientific stack including NumPy, Pandas, Matplotlib, SciPy, and
scikit-learn. The [`packages`
directory](https://github.com/pyodide/pyodide/tree/master/packages) lists over
75 packages which are currently available. In addition it's possible to install
pure Python wheels from PyPi.

**Pyodide** provides transparent conversion of objects between Javascript and
Python. When used inside a browser, Python has full access to the Web APIs.

While closely related to the [iodide project](https://iodide.io), a tool for
*literate scientific computing and communication for the web*, Pyodide goes
beyond running in a notebook environment. To maximize the flexibility of the
modern web, **Pyodide** may be used standalone in any context where you want to
**run Python inside a web browser**.

## Try Pyodide (no installation needed)

Try Pyodide in [Python REPL](https://pyodide-cdn2.iodide.io/v0.17.0a2/full/console.html) directly in your
browser.

For further information, look through the [documentation](https://pyodide.org/en/0.17.0a2/).

## Getting Started

Pyodide offers three different ways to get started depending on your needs and
technical resources. These include:

- Use a hosted distribution of Pyodide: see [using pyodide from
  Javascript](https://pyodide.org/en/0.17.0a2/usage/quickstart.html)
  documentation.
- Download a version of Pyodide from the [releases
  page](https://github.com/pyodide/pyodide/releases/) and serve it
  with a web server.
- [Build Pyodide from source](https://pyodide.org/en/0.17.0a2/development/building-from-sources.html)
  - Build natively with `make`: primarily for Linux users who want to
    experiment or contribute back to the project.
  - [Use a Docker image](https://pyodide.org/en/0.17.0a2/development/building-from-sources.html#using-docker):
    recommended for Windows and macOS users and for Linux users who prefer a
    Debian-based Docker image with the dependencies already installed.

## Contributing

Please view the
[contributing guide](https://pyodide.org/en/0.17.0a2/development/contributing.html)
for tips on filing issues, making changes, and submitting pull requests.

## License

Pyodide uses the Mozilla Public License Version 2.0. See the
[LICENSE file](LICENSE) for more details.
