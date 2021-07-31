cffi-example: an example project showing how to use Python's CFFI
=================================================================

A complete project which demonstrates how to use CFFI 1.0 during development of
a modern Python package:

* Development
* Testing across Python interpreters (Py2, Py3, PyPy)
* Packaging and distribution


Status
------

This repository is the result of a weeks worth of frustrated googling. I don't
think anything is *too* misleading, but I would deeply appreciate feedback from
anyone who actually knows what's going on.


Examples
--------

* ``cffi_example/person.py`` and ``cffi_example/build_person.py`` is an example
  of a Python class which wraps a C class, including proper memory management
  and passing around string buffers::

    >>> p = Person(u"Alex", u"Smith", 72) # --> calls person_create(...)
    >>> p.get_full_name() # --> calls person_get_full_name(p, buf, len(buf))
    u"Alex Smith"

* ``cffi_example/fnmatch.py`` and ``cffi_example/build_fnmatch.py`` is an
  example of wrapping a shared library (in this case ``libc``'s `fnmatch`__)::

    >>> fnmatch("f*", "foo") # --> calls libc's fnmatch
    True

__ http://man7.org/linux/man-pages/man3/fnmatch.3.html


Development
-----------

1. Clone the repository::

    $ git clone git@github.com:wolever/python-cffi-example.git

2. Make sure that ``cffi``, ``py.test``, and ``tox`` are installed::

    $ pip install -r requirements-testing.txt

3. Run ``python setup.py develop`` to build development versions of the
   modules::

    $ python setup.py develop
    ...
    Finished processing dependencies for cffi-example==0.1

4. Test locally with ``py.test``::

    $ py.test test/
    =========================== test session starts ===========================
    platform darwin -- Python 2.7.2 -- py-1.4.28 -- pytest-2.7.1
    rootdir: /Users/wolever/code/python-cffi-example, inifile:
    collected 7 items

    test/test_fnmatch.py ....
    test/test_person.py ...

    ======================== 7 passed in 0.03 seconds =========================

5. Test against multiple Python environments using ``tox``::

    $ tox
    ...
    _________________________________ summary _________________________________
    py26: commands succeeded
    py27: commands succeeded
    py33: commands succeeded
    pypy: commands succeeded
    congratulations :)

6. I prefer to use ``make`` to clean and rebuild libraries during development
   (since it's faster than ``setup.py develop``)::

    $ make clean
    ...
    $ make
    python cffi_example/build_person.py
    python cffi_example/build_fnmatch.py


Packaging
---------

This example uses `CFFI's recommended combination`__ of ``setuptools`` and
``cffi_modules``::

    $ cat setup.py
    from setuptools import setup

    setup(
        ...
        install_requires=["cffi>=1.0.0"],
        setup_requires=["cffi>=1.0.0"],
        cffi_modules=[
            "./cffi_example/build_person.py:ffi",
            "./cffi_example/build_fnmatch.py:ffi",
        ],
    )

__ https://cffi.readthedocs.org/en/latest/cdef.html#distutils-setuptools

This will cause the modules to be built with ``setup.py develop`` or ``setup.py
build``, and installed with ``setup.py install``.

**Note**: Many examples you'll see online use either the ``distutils``
``ext_modules=[cffi_example.ffi.distribute_extension()]`` method, or the
more complex ``keywords_with_side_effects`` method. To the best of my
knowledge these methods are only necessary with CFFI < 1.0 or ``distutils``.
`dstufft`__ has written a fantastic post —
https://caremad.io/2014/11/distributing-a-cffi-project/ — which details the
drawbacks of the ``ext_modules`` method and explains the
``keywords_with_side_effects`` method, but I believe it was written before CFFI
1.0 so it does not include the now preferred ``cffi_modules`` method.

__ https://twitter.com/dstufft/


Distribution
------------

Distribution is just like any other Python package, with the obvious caveat
that wheels will be platform-specific::

    $ python setup.py sdist bdist_wheel
    ...
    $ ls dist/
    cffi-example-0.1.tar.gz
    cffi_example-0.1-cp27-none-macosx_10_8_intel.whl

And the package can be uploaded to PyPI using ``upload``::

    $ python setup.py sdist upload


Note that users of the source package will need to have ``cffi`` (and a C
compiler, and development headers of any libraries you're linking against)
installed to build and install your package.

Note also that the ``MANIFEST.in`` file will need to be updated to include any
new source or headers you may add during development. The ``tox`` tests will
catch this error, but it may not be obvious how to correct it.


Caveats
-------

* Doesn't yet cover using ``dlopen(...)`` to dynamically load ``.so`` files
  because I haven't figured out any best practices for building custom shared
  libraries along with a Python package's lifecycle, and the
  `CFFI documentation on loading dynamic libraries`__ covers the details of
  making the ``lib.dlopen(...)`` call.

* Using ``make`` to build modules during development is less than ideal. Please
  post here if there's a better way to do this:
  http://stackoverflow.com/q/30823397/71522


__ https://cffi.readthedocs.org/en/latest/overview.html#out-of-line-abi-level
