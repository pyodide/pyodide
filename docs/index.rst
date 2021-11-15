Pyodide
=======

Python with the scientific stack, compiled to WebAssembly.

Pyodide may be used in any context where you want to run Python inside a web
browser.

Pyodide brings the Python 3.9 runtime to the browser via WebAssembly, thanks to
`Emscripten <https://emscripten.org/>`_.
It builds the Python scientific stack including NumPy, Pandas, Matplotlib, SciPy, and
scikit-learn. Over 75 packages are currently available. In addition, it's
possible to install pure Python wheels from PyPI.

Pyodide provides transparent conversion of objects between JavaScript and
Python. When used inside a browser, Python has full access to the Web APIs.

Pyodide development happens on GitHub: `github.com/pyodide/pyodide <https://github.com/pyodide/pyodide>`_

Try Pyodide (no installation needed)
------------------------------------

Try Pyodide in a
`REPL <https://pyodide.org/en/stable/console.html>`_ directly in
your browser.


Table of contents
-----------------

Using Pyodide
^^^^^^^^^^^^^

.. toctree::
   :maxdepth: 1

   usage/quickstart.md
   usage/downloading-and-deploying.md
   usage/index.md
   usage/loading-packages.md
   usage/type-conversions.md
   usage/wasm-constraints.md
   usage/keyboard-interrupts.md
   usage/api-reference.md
   usage/faq.md

Development
^^^^^^^^^^^

The Development section help Pyodide contributors to find information about the
development process including making packages to support third party libraries.

.. toctree::
   :maxdepth: 1
   :caption: Development

   development/building-from-sources.md
   development/new-packages.md
   development/contributing.md
   development/testing.md
   development/debugging.md


Project
^^^^^^^

The Project section gives additional information about the project's
organization and latest releases.

.. toctree::
   :maxdepth: 1
   :caption: Project

   project/about.md
   project/roadmap.md
   project/code-of-conduct.md
   project/governance.md
   project/changelog.md
   project/related-projects.md


Communication
-------------

- Blog: `blog.pyodide.org <https://blog.pyodide.org/>`_
- Mailing list: `mail.python.org/mailman3/lists/pyodide.python.org/ <https://mail.python.org/mailman3/lists/pyodide.python.org/>`_
- Gitter: `gitter.im/pyodide/community <https://gitter.im/pyodide/community>`_
- Twitter: `twitter.com/pyodide <https://twitter.com/pyodide>`_
- Stack Overflow: `stackoverflow.com/questions/tagged/pyodide <https://stackoverflow.com/questions/tagged/pyodide>`_
