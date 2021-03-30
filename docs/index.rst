.. Pyodide documentation master file, created by
   sphinx-quickstart on Sun Jun  9 12:22:53 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pyodide
=======

Python with the scientific stack, compiled to WebAssembly.

.. note::

   Pyodide bundles support for the following packages: numpy, scipy, and
   many other libraries in the Python scientific stack.

   To use additional packages from PyPI, see
   :ref:`micropip` .

   You can also :ref:`create a Pyodide package <new-packages>` to support and share libraries for new
   applications.

Using Pyodide
=============

Pyodide may be used in several ways: directly from JavaScript, or to execute
Python scripts asynchronously in a web worker. Additional pure Python packages
may be installed from PyPI to be used with Pyodide.

.. toctree::
   :maxdepth: 2

   usage/quickstart.md
   usage/webworker.md
   usage/serving-pyodide-packages.md
   usage/loading-packages.md
   usage/type-conversions.md
   usage/api-reference.md
   usage/faq.md

Developing Pyodide
==================

The Development section help Pyodide contributors to find information about the
development process including making packages to support third party libraries
and understanding type conversions between Python and JavaScript.

The Project section helps contributors get started and gives additional
information about the project's organization.

.. toctree::
   :maxdepth: 1
   :caption: Development

   development/building-from-sources.md
   development/new-packages.md
   development/contributing.md
   development/core.md
   development/testing.md

.. toctree::
   :titlesonly:
   :caption: Project

   project/about.md
   project/code-of-conduct.md
   project/governance.md
   project/changelog.md
   project/related-projects.md

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
