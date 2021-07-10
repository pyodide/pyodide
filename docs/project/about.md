# About Pyodide

Python with the scientific stack, compiled to WebAssembly.

Pyodide may be used in any context where you want to run Python inside a web
browser.

Pyodide brings the Python 3.9 runtime to the browser via WebAssembly, along with
the Python scientific stack including NumPy, Pandas, Matplotlib, SciPy, and
scikit-learn. The [packages
directory](https://github.com/pyodide/pyodide/tree/main/packages) lists over
75 packages which are currently available. In addition it's possible to install
pure Python wheels from PyPi.

Pyodide provides transparent conversion of objects between Javascript and
Python. When used inside a browser, Python has full access to the Web APIs.

## History
Pyodide was created in 2018 by [Michael Droettboom](https://github.com/mdboom)
at Mozilla as part of the [Iodide
project](https://github.com/iodide-project/iodide). Iodide is an experimental
web-based notebook environment for literate scientific computing and
communication.

## Contributing

See the {ref}`contributing guide <how_to_contribute>` for tips on filing issues,
making changes, and submitting pull requests. Pyodide is an independent and
community-driven open-source project. The decision making process is outlined in
{ref}`project-governance`.

## Communication

- Mailing list: [mail.python.org/mailman3/lists/pyodide.python.org/](https://mail.python.org/mailman3/lists/pyodide.python.org/)
- Gitter: [gitter.im/pyodide/community](https://gitter.im/pyodide/community)
- Twitter: [twitter.com/pyodide](https://twitter.com/pyodide)
- Stack Overflow: [stackoverflow.com/questions/tagged/pyodide](https://stackoverflow.com/questions/tagged/pyodide)

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).

## Infrastructure support

We would like to thank,
 - [Mozilla](https://www.mozilla.org/en-US/) and
[CircleCl](https://circleci.com/) for Continuous Integration resources
 - [JsDelivr](https://www.jsdelivr.com/) for providing a CDN for Pyodide
   packages
 - [ReadTheDocs](https://readthedocs.org/) for hosting the documentation.
