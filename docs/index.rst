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
   applications, try `Creating a Pyodide package <new_packages.html>`_.

Using Pyodide
=============

Pyodide may be used in several ways, including in an Iodide notebook, directly
from JavaScript, or to execute Python scripts asynchronously in a web worker.
Although still experimental, additional packages may be installed from PyPI
to be used with Pyodide.

.. toctree::
   :maxdepth: 1
   :caption: Usage

   using_pyodide_from_iodide.md
   using_pyodide_from_javascript.md
   using_pyodide_from_webworker.md

.. toctree::
   :maxdepth: 1
   :caption: Extending

   pypi.md
   api_reference.md

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

   building_from_sources.md
   new_packages.md
   type_conversions.md
   contributing.md
   testing.md

.. toctree::
   :titlesonly:
   :caption: Project

   about.md
   code-of-conduct
   changelog.md

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
