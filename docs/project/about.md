# What is Pyodide?

Pyodide is a Python distribution for the browser and Node.js based on WebAssembly/[Emscripten](https://emscripten.org/).

Pyodide makes it possible to install and run Python packages in the browser with
[micropip](https://pyodide.org/en/stable/usage/api/micropip-api.html). Any pure
Python package with a wheel available on PyPI is supported. Many packages with C
extensions have also been ported for use with Pyodide. These include many
general-purpose packages such as regex, PyYAML, lxml and scientific Python
packages including NumPy, pandas, SciPy, Matplotlib, and scikit-learn.

Pyodide comes with a robust Javascript 🡘 Python foreign function interface so
that you can freely mix these two languages in your code with minimal
friction. This includes full support for error handling (throw an error in one
language, catch it in the other), async/await, and much more.

When used inside a browser, Python has full access to the Web APIs.

## History

Pyodide was created in 2018 by [Michael Droettboom](https://github.com/mdboom)
at Mozilla as part of the [Iodide
project](https://github.com/iodide-project/iodide). Iodide is an experimental
web-based notebook environment for literate scientific computing and
communication.

## Contributing

See the {ref}`contributing guide <how_to_contribute>` for tips on filing issues,
making changes, and submitting pull requests. Pyodide is an independent and
community-driven open-source project. The decision-making process is outlined in
{ref}`project-governance`.

## Citing

If you use Pyodide for a scientific publication, we would appreciate citations.
Please find us [on Zenodo](https://zenodo.org/record/5156931) and use the citation
for the version you are using. You can replace the full author
list from there with "The Pyodide development team" like in the example below:

```
@software{pyodide_2021,
  author       = {The Pyodide development team},
  title        = {pyodide/pyodide},
  month        = aug,
  year         = 2021,
  publisher    = {Zenodo},
  version      = {0.27.4},
  doi          = {10.5281/zenodo.5156931},
  url          = {https://doi.org/10.5281/zenodo.5156931}
}
```

## Communication

- Blog: [blog.pyodide.org](https://blog.pyodide.org/)
- Mailing list: [mail.python.org/mailman3/lists/pyodide.python.org/](https://mail.python.org/mailman3/lists/pyodide.python.org/)
- Twitter: [twitter.com/pyodide](https://twitter.com/pyodide)
- Stack Overflow: [stackoverflow.com/questions/tagged/pyodide](https://stackoverflow.com/questions/tagged/pyodide)
- Discord: [Pyodide Discord](https://dsc.gg/pyodide)

## Donations

We accept donations to the Pyodide project at
[opencollective.com/pyodide](https://opencollective.com/pyodide). All donations
are processed by the [Open Source Collective](https://www.oscollective.org/) -- a
nonprofit organization that acts as our fiscal host.

Funds will be mostly spent to organize in-person code sprints and to cover
infrastructure costs for distributing packages built with Pyodide.

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
