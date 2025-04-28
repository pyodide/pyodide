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

### Institutional Support

- **Mozilla** — Core development support
- **NSF Grant** — Research and Development support

### Sponsors

You can support Pyodide development by sponsoring us on:

1. [Sponsor us on GitHub](https://github.com/sponsors/pyodide)
2. [Sponsor us on OpenCollective](https://opencollective.com/pyodide#sponsor)

|                                        [GitHub Sponsors](https://github.com/sponsors)                                        |                                              [Suborbital](https://suborbital.dev)                                               |                                         [Hugging Face](https://huggingface.co)                                          |                                          [Posit](https://posit.co)                                          |
| :--------------------------------------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------: |
| <img src="https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png" alt="GitHub Sponsors" width="72" height="72"> | <img src="https://avatars.githubusercontent.com/u/54323182?s=200&v=4" alt="Suborbital Software Systems" width="72" height="72"> | <img src="https://huggingface.co/front/assets/huggingface_logo-noborder.svg" alt="Hugging Face" width="72" height="72"> | <img src="https://posit.co/wp-content/uploads/2022/10/thumbnail-63.jpg" alt="Posit" width="72" height="72"> |

|                                            [PyCafe](https://py.cafe)                                            |                             [Eduwalks](https://opencollective.com/eduwalks)                             |                                  [Mausbrand](https://mausbrand.com)                                   |
| :-------------------------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------: |
| <img src="https://py.cafe/logos/pycafe_logo.png" alt="PyCafe" width="72" height="72" style="background:white;"> | <img src="https://dummyimage.com/72x72/ffffff/000000.png&text=E" alt="Eduwalks" width="72" height="72"> | <img src="https://www.mausbrand.com/static/images/banner.jpg" alt="Mausbrand" width="72" height="72"> |

### Backers

We're grateful to all our backers who support our project! If you'd like to become a backer:

<a href="https://opencollective.com/pyodide#backers" target="_blank">
  <img src="https://opencollective.com/pyodide/backers.svg?width=890" alt="Backers">
</a>

## License

Pyodide uses the [Mozilla Public License Version
2.0](https://choosealicense.com/licenses/mpl-2.0/).
