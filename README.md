<div align="center">
  <a href="https://github.com/pyodide/pyodide">
  <img src="./docs/_static/img/pyodide-logo-readme.png" alt="Pyodide">
  </a>
</div>

[![NPM Latest Release](https://img.shields.io/npm/v/pyodide)](https://www.npmjs.com/package/pyodide)
[![PyPI Latest Release](https://img.shields.io/pypi/v/pyodide-py.svg)](https://pypi.org/project/pyodide-py/)
[![Build Status](https://circleci.com/gh/pyodide/pyodide.png)](https://circleci.com/gh/pyodide/pyodide)
[![Documentation Status](https://readthedocs.org/projects/pyodide/badge/?version=stable)](https://pyodide.readthedocs.io/?badge=stable)

Pyodide is a Python distribution for the browser and Node.js based on WebAssembly.

## What is Pyodide?

Pyodide is a port of CPython to WebAssembly/[Emscripten](https://emscripten.org/).

Pyodide makes it possible to install and run Python packages in the browser with
[micropip](https://micropip.pyodide.org/). Any pure Python package with a wheel
available on PyPi is supported. Many packages with C, C++, and Rust extensions
have also been ported for use with Pyodide. These include many general-purpose
packages such as regex, PyYAML, and cryptography, and scientific Python packages
including NumPy, pandas, SciPy, Matplotlib, and scikit-learn.

Pyodide comes with a robust Javascript ⟺ Python foreign function interface so
that you can freely mix these two languages in your code with minimal friction.
This includes full support for error handling, async/await, and much more.

When used inside a browser, Python has full access to the Web APIs.

## Try Pyodide (no installation needed)

Try Pyodide in a
[REPL](https://pyodide.org/en/stable/console.html) directly in
your browser. For further information, see the
[documentation](https://pyodide.org/en/stable/).

## Getting Started

- If you wish to use a hosted distribution of Pyodide: see the [Getting
  Started](https://pyodide.org/en/stable/usage/quickstart.html) documentation.
- If you wish to host Pyodide yourself, you can download Pyodide from the [releases
  page](https://github.com/pyodide/pyodide/releases/) and serve it with a web server.
- If you wish to use Pyodide with a bundler, see [the documentation on Working with
  Bundlers](https://pyodide.org/en/stable/usage/working-with-bundlers.html)
- If you are a Python package maintainer, see [the documentation on building and testing Python
  packages](https://pyodide.org/en/stable/development/building-and-testing-packages.html).
- If you want to add a package to the Pyodide distribution, [see the documentation on adding
  a package to the Pyodide distribution](https://pyodide.org/en/stable/development/new-packages.html)
- If you wish to experiment or contribute back to the Pyodide runtime, see the documentation on
  [building Pyodide from source](https://pyodide.org/en/stable/development/building-from-sources.html)

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
independent and community-driven open-source project. The decision-making
process is outlined in the [Project
governance](https://pyodide.org/en/stable/project/governance.html).

## Communication

- Blog: [blog.pyodide.org](https://blog.pyodide.org/)
- Mailing list: [mail.python.org/mailman3/lists/pyodide.python.org/](https://mail.python.org/mailman3/lists/pyodide.python.org/)
- Twitter: [twitter.com/pyodide](https://twitter.com/pyodide)
- Stack Overflow: [stackoverflow.com/questions/tagged/pyodide](https://stackoverflow.com/questions/tagged/pyodide)
- Discord: [Pyodide Discord](https://dsc.gg/pyodide)

## Sponsors

For a full list of current and historical sponsors, please see the [Funding](https://pyodide.org/en/stable/project/about.html#funding) section of our About page.

Pyodide also has a large number of small donors. If you’re interested in supporting Pyodide, check out our [OpenCollective](https://opencollective.com/pyodide) and [GitHub Sponsors](https://github.com/sponsors/pyodide) pages.

### Special thanks

- [BrowserStack](https://www.browserstack.com/): This project is tested with BrowserStack

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).

## Running tests in parallel

To speed up test execution, you can use pytest-xdist:

```
pytest -n auto
```

This will run tests in parallel using all available CPU cores.
