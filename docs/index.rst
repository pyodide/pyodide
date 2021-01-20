.. Pyodide documentation master file, created by
   sphinx-quickstart on Sun Jun  9 12:22:53 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pyodide
=======

The Python scientific stack, compiled to WebAssembly.

.. note::

   Pyodide bundles support for the following packages: numpy, scipy, and
   many other libraries in the Python scientific stack.

   To use additional packages from PyPI, try the experimental feature,
   `Installing packages from PyPI <pypi.html>`_ and try to `pip install` the
   package.

   To create a Pyodide package to support and share libraries for new
   applications, try `Creating a Pyodide package <new-packages.html>`_.

Using Pyodide
=============

Pyodide may be used in several ways: directly from JavaScript, or to execute
Python scripts asynchronously in a web worker. Although still experimental,
additional packages may be installed from PyPI to be used with Pyodide.

.. toctree::
   :maxdepth: 2
   :caption: Usage

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
   project/changelog.md

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
