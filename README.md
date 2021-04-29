<div align="center">
  <a href="https://github.com/pyodide/pyodide">
  <img src="./docs/_static/img/pyodide-logo-readme.png" alt="Pyodide">
  </a>
</div>


[![Build Status](https://circleci.com/gh/pyodide/pyodide.png)](https://circleci.com/gh/pyodide/pyodide)
[![Documentation Status](https://readthedocs.org/projects/pyodide/badge/?version=stable)](https://pyodide.readthedocs.io/?badge=stable)

Python with the scientific stack, compiled to WebAssembly.

## What is Pyodide?

Pyodide may be used in any context where you want to run Python inside a web
browser.

Pyodide brings the Python 3.8 runtime to the browser via WebAssembly, along with
the Python scientific stack including NumPy, Pandas, Matplotlib, SciPy, and
scikit-learn. The [packages directory](packages) lists over 75 packages which
are currently available. In addition it's possible to install pure Python wheels
from PyPi.

Pyodide provides transparent conversion of objects between Javascript and
Python. When used inside a browser, Python has full access to the Web APIs.

## Try Pyodide (no installation needed)

Try Pyodide in a
[REPL](https://pyodide.org/en/stable/console.html) directly in
your browser. For further information, see the
[documentation](https://pyodide.org/en/stable/).

## Getting Started

Pyodide offers three different ways to get started depending on your needs and
technical resources. These include:

- Use a hosted distribution of Pyodide: see the [Getting
  Started](https://pyodide.org/en/stable/usage/quickstart.html) documentation.
- Download a version of Pyodide from the [releases
  page](https://github.com/pyodide/pyodide/releases/) and serve it
  with a web server.
- [Build Pyodide from source](https://pyodide.org/en/stable/development/building-from-sources.html)
  - Build natively with `make`: primarily for Linux users who want to
    experiment or contribute back to the project.
  - [Use a Docker image](https://pyodide.org/en/stable/development/building-from-sources.html#using-docker):
    recommended for Windows and macOS users and for Linux users who prefer a
    Debian-based Docker image with the dependencies already installed.


## History
Pyodide was created in 2018 by [Michael Droettboom](https://github.com/mdboom)
at Mozilla as part of the [Iodide
project](https://github.com/iodide-project/iodide). Iodide is an experimental
web-based notebook environment for literate scientific computing and
communication.

Iodide is no longer maintained. If you want to use Pyodide in an interactive
client-side notebook, see [Pyodide notebook
environments](https://pyodide.org/en/stable/project/related-projects.html#notebook-environments-ides-repls).

## Contributing

Please view the [contributing
guide](https://pyodide.org/en/stable/development/contributing.html) for tips
on filing issues, making changes, and submitting pull requests. Pyodide is an
independent and community-driven open-source project. The decision making
process is outlined in the [Project
governance](https://pyodide.org/en/stable/project/governance.html).

## Communication

- Mailing list: [mail.python.org/mailman3/lists/pyodide.python.org/](https://mail.python.org/mailman3/lists/pyodide.python.org/)
- Gitter: [gitter.im/pyodide/community](https://gitter.im/pyodide/community)
- Twitter: [twitter.com/pyodide](https://twitter.com/pyodide)
- Stack Overflow: [stackoverflow.com/questions/tagged/pyodide](https://stackoverflow.com/questions/tagged/pyodide)

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).
