# Core

## CPython APIs

### Conventions for indicating errors
The two main ways to indicate errors:
1. If the function returns a pointer, (usually PyObject*) then to indicate an error set an exception and return NULL.
2. If the function returns int and the output is nonnegative, to indicate an error set an exception and return NULL.

Certain functions have "successful errors" like ``PyIter_Next`` (successful error is "StopIteration") and ``PyDict_GetItemWithError`` (successful error is "KeyError"). These functions will return NULL without setting an exception to indicate the "successful error" occurred. Check what happened with ``PyErr_Occurred``. Also, functions that return ``int`` for which ``-1`` is a valid return value will return ``-1`` with no error set to indicate that the result is ``-1`` and ``-1`` with an error set if an error did occur. The simplest way to handle this is to always check ``PyErr_Occurred``.

Lastly, the argument parsing functions ``PyArg_ParseTuple``, ``PyArg_Parse``, etc behave weirdly. These return ``true`` on success and return ``false`` and set an error on failure.


### APIs to avoid:

1. ``PyDict_GetItem``, ``PyDict_GetItemString``, and ``_PyDict_GetItemId``

Instead use ``PyDict_GetItemWithError`` and ``_PyDict_GetItemIdWithError``.

2. ``PyObject_HasAttrString``, ``PyObject_GetAttrString``,  ``PyDict_GetItemString``, ``PyDict_SetItemString``, ``PyMapping_HasKeyString`` etc, etc.

If the string you are using is a constant: ``PyDict_GetItemString(dict, "identifier")``, then make an id with ``Py_Identifier(identifier)`` and then use ``_PyDict_GetItemId(&PyId_identifier)``. If the string is not constant, convert it to a python object with ``PyUnicode_FromString()`` and then use e.g., ``PyDict_GetItem``.

3. ``PyModule_AddObject``. This steals a reference on success but not on failure and requires unique cleanup code.
