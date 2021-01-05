# Core

## Structure of functions

It takes special care to correctly and cleanly handle both reference counting and exceptions.
To do this, we divide any function that produces more than a couple of owned ``PyObject*``s or ``JsRef``s into several "segments".
The more owned references there are in a function and the longer it is, the more important it becomes to follow this style carefully.
By being as consistent as possible, we reduce the burden on people reading the code to double check that you are not leaking memory or errors. In short functions it is fine to do something ad hoc.

1. The guard block. The first block of a function does sanity checks on the inputs and ArgParsing, but only to
the extent possible without creating any owned references. If you check more complicated invariants on the inputs in a way that requires creating owned references, this logic belongs in the body block.

Here's an exmaple of a ``METH_VARARGS`` function:
```C
PyObject*
JsImport_CreateModule(PyObject* self, PyObject* args)
{
  // Guard
  PyObject* name;
  PyObject* jsproxy;
  if (!PyArg_UnpackTuple(args, "create_module", 2, 2, &spec, &jsproxy)) {
    return NULL;
  }
  if (!JsProxy_Check(jsproxy)) {
    PyErr_SetString(PyExc_TypeError, "package is not an instance of jsproxy");
    return NULL;
  }
```


2. Forward declaration of owned references. This starts by declaring a success flag ``bool success = false``. This will be used in the finally block to decide whether the finally block was entered after a successful execution or after an error. Then declare every reference counted variable that we will create during execution of the function. Finally, declare the variable that we are planning to return.
Typically this will be called ``result``, but in this case the function is named ``CreateModule`` so we name the return variable ``module``.

```C
  bool success = false;
  // Note: these are all of the objects that we will own. If a function returns
  // a borrow, we incref the result so that we can free it in the finally block.
  // Reference counting is hard, so it's good to be as explicit and consistent
  // as possible!
  PyObject* sys_modules = NULL;
  PyObject* importlib_machinery = NULL;
  PyObject* ModuleSpec = NULL;
  PyObject* spec = NULL;
  PyObject* __dir__ = NULL;
  PyObject* module_dict = NULL;
  // result
  PyObject* module = NULL;
  ```

3. The body of the function. The vast majority of API calls can return error codes. You MUST check every fallible API for an error. In the most typical case you can do this using the macros QUIT_IF_NULL() for APIs that return a pointer and QUIT_IF_MINUS_ONE() for APIs that return an int. There is also ``QUIT()`` for an unconditional ``goto finally`` and ``QUIT_IF_ERR_OCCURRED()`` which quits if ``PyErr_Occurred``. These macros will ``goto finally`` if the error condition is hit. Furthermore, check every API that returns a reference for whether it returns a borrowed reference or an owned one. If it returns a borrowed reference, immediately `Py_XINCREF()` the result to convert it into an owned reference (before ``QUIT_IF_NULL``, this is to be consistent with the case where you use custom error handling).

```C
  name = PyUnicode_FromString(name_utf8);
  QUIT_IF_NULL(name);
  sys_modules = PyImport_GetModuleDict(); // returns borrow
  Py_XINCREF(sys_modules);
  QUIT_IF_NULL(sys_modules);
  module = PyDict_GetItemWithError(sys_modules, name); // returns borrow
  Py_XINCREF(module);
  if(module && !JsImport_Check(module)){
    PyErr_Format(PyExc_KeyError,
      "Cannot mount with name '%s': there is an existing module by this name that was not mounted with 'pyodide.mountPackage'."
      , name
    );
    QUIT();
  }
  QUIT_IF_ERR_OCCURRED();
// ... [SNIP]
```

4. The finally block. Here we will clear all the variables we declared at the top. Do not clear the arguments! They are borrowed. According to the standard Python function calling convention, the calling code will clear them for you.
```
  success = true;
finally:
  Py_CLEAR(sys_modules);
  Py_CLEAR(importlib_machinery);
  Py_CLEAR(ModuleSpec);
  Py_CLEAR(spec);
  Py_CLEAR(__dir__);
  Py_CLEAR(module_dict);
  if(!success){
    Py_CLEAR(result);
  }
  return result;
}
```


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
Instead use ``PyObject_SetAttr``.

## Testing
TODO.
See "core/testing.h", which defines macros useful for testing.

### DEFINE_TEST

### DEFINE_TEST_EXPECT_FAIL

### ASSERT
