# About the Project

The Python scientific stack, compiled to WebAssembly.

Pyodide brings the Python runtime to the browser via WebAssembly, along with
the Python scientific stack including NumPy, Pandas, Matplotlib, parts of
SciPy, and NetworkX. The [packages
directory](https://github.com/iodide-project/pyodide/tree/master/packages)
lists over 75 packages which are currently available. In addition it's possible
to install pure Python wheels from PyPi.

Pyodide provides transparent conversion of objects between Javascript and
Python. When used inside a browser, Python has full access to the Web APIs.

## History

Pyodide was created in 2018 by [Michael Droettboom](https://github.com/mdboom)
at Mozilla as part of the [iodide project](https://github.com/iodide-project/iodide), a set of experiments around
scientific computing and communication for the web.

At present Pyodide is an independent and community driven open-source project.
The decision making process is outlined in the {ref}`project governance <project-governance>`.
Pyodide may be used standalone in any context where you want to run Python
inside a web browser.

## Infrastructure support

We would also like to thank,
 - [Mozilla](https://www.mozilla.org/en-US/) and
[CircleCl](https://circleci.com/) for Continuous Integration resources
 - [JsDelivr](https://www.jsdelivr.com/) for providing a CDN for pyodide packages
 - [ReadTheDocs](https://readthedocs.org/) for hosting the documentation.
