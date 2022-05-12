Pyodide
=======


Pyodide is a Python distribution for the browser and Node.js based on WebAssembly.

What is Pyodide?
----------------

Pyodide is a port of CPython to WebAssembly/`Emscripten <https://emscripten.org/>`_.

Pyodide makes it possible to install and run Python packages in the browser with
`micropip <https://pyodide.org/en/stable/usage/api/micropip-api.html>`_. Any pure
Python package with a wheel available on PyPI is supported. Many packages with C
extensions have also been ported for use with Pyodide. These include many
general-purpose packages such as regex, pyyaml, lxml and scientific Python
packages including numpy, pandas, scipy, matplotlib, and scikit-learn.

Pyodide comes with a robust Javascript ⟺ Python foreign function interface so
that you can freely mix these two languages in your code with minimal
friction. This includes full support for error handling (throw an error in one
language, catch it in the other), async/await, and much more.

When used inside a browser, Python has full access to the Web APIs.

Try Pyodide
-----------

Try Pyodide in a
`REPL <https://pyodide.org/en/stable/console.html>`_ directly in
your browser (no installation needed).


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

The Development section helps Pyodide contributors to find information about the
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
