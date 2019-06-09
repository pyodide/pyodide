.. Pyodide documentation master file, created by
   sphinx-quickstart on Sun Jun  9 12:22:53 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pyodide
=======

The Python scientific stack, compiled to WebAssembly.

.. note::

   Pyodide bundles support for the following packages: numpy, scipy, ...

   If you would like to use additional packages, try the experimental feature,
   *Installing packages from PyPI* to `pip install` a package.
   To create a Pyodide package to support and share libraries new applications,
   try *Creating a Pyodide package*.

Using Pyodide
=============

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

This section help Pyodide contributors to find information about the development process including making packages to
support third party libraries and understanding type conversions between Python and JavaScript.


.. toctree::
   :maxdepth: 1
   :caption: Development

   new_packages.md
   type_conversions.md

.. toctree::
   :titlesonly:
   :caption: Project

   rootdir.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
