(contributing-core)=

# Contributing to the "core" C Code

This file is intended as guidelines to help contributors trying to modify the C source files in `src/core`.

## What the files do

The primary purpose of `core` is to implement {ref}`type translations <type-translations>` between Python and JavaScript. Here is a breakdown of the purposes of the files.

- `main` -- responsible for configuring and initializing the Python interpreter, initializing the other source files, and creating the `_pyodide_core` module which is used to expose Python objects to `pyodide_py`. `main.c` also tries to generate fatal initialization error messages to help with debugging when there is a mistake in the initialization code.
- `keyboard_interrupt` -- This sets up the keyboard interrupts system for using Pyodide with a webworker.

### Backend utilities

- `hiwire` -- A helper framework. It is impossible for wasm to directly hold owning references to JavaScript objects. The primary purpose of hiwire is to act as a surrogate owner for JavaScript references by holding the references in a JavaScript `Map`. `hiwire` also defines a wide variety of `EM_JS` helper functions to do JavaScript operations on the held objects. The primary type that hiwire exports is `JsRef`. References are created with `Module.hiwire.new_value` (only can be done from JavaScript) and must be destroyed from C with `hiwire_decref` or `hiwire_CLEAR`, or from JavaScript with `Module.hiwire.decref`.
- `error_handling` -- defines macros useful for error propagation and for adapting JavaScript functions to the CPython calling convention. See more in the {ref}`error_handling_macros` section.

### Type conversion from JavaScript to Python

- `js2python` -- Translates basic types from JavaScript to Python, leaves more complicated stuff to jsproxy.
- `jsproxy` -- Defines Python classes to proxy complex JavaScript types into Python. A complex file responsible for many of the core behaviors of Pyodide.

### Type conversion from Python to JavaScript

- `python2js` -- Translates types from Python to JavaScript, implicitly converting basic types and creating pyproxies for others. It also implements explicity conversion from Python to JavaScript (the `toJs` method).
- `python2js_buffer` -- Attempts to convert Python objects that implement the Python [Buffer Protocol](https://docs.python.org/3/c-api/buffer.html). This includes `bytes` objects, `memoryview`s, `array.array` and a wide variety of types exposed by extension modules like `numpy`. If the data is a 1d array in a contiguous block it can be sliced directly out of the wasm heap to produce a JavaScript `TypedArray`, but JavaScript does not have native support for pointers, so higher dimensional arrays are more complicated.
- `pyproxy` -- Defines a JavaScript `Proxy` object that passes calls through to a Python object. Another important core file, `PyProxy.apply` is the primary entrypoint into Python code. `pyproxy.c` is much simpler than `jsproxy.c` though.

## CPython APIs

### Conventions for indicating errors

The two main ways to indicate errors:

1. If the function returns a pointer, (most often `PyObject*`, `char*`, or `const char*`) then to indicate an error set an exception and return `NULL`.
2. If the function returns `int` or `float` and a correct output must be nonnegative, to indicate an error set an exception and return `-1`.

Certain functions have "successful errors" like `PyIter_Next` (successful error is `StopIteration`) and `PyDict_GetItemWithError` (successful error is `KeyError`). These functions will return `NULL` without setting an exception to indicate the "successful error" occurred. Check what happened with `PyErr_Occurred`. Also, functions that return `int` for which `-1` is a valid return value will return `-1` with no error set to indicate that the result is `-1` and `-1` with an error set if an error did occur. The simplest way to handle this is to always check `PyErr_Occurred`.

Lastly, the argument parsing functions `PyArg_ParseTuple`, `PyArg_Parse`, etc are edge cases. These return `true` on success and return `false` and set an error on failure.

### Python APIs to avoid:

- `PyDict_GetItem`, `PyDict_GetItemString`, and `_PyDict_GetItemId`
  These APIs do not do correct error reporting and there is talk in the Python community of deprecating them going forward. Instead, use `PyDict_GetItemWithError` and `_PyDict_GetItemIdWithError` (there is no `PyDict_GetItemStringWithError` API because use of `GetXString` APIs is also discouraged).

- `PyObject_HasAttrString`, `PyObject_GetAttrString`, `PyDict_GetItemString`, `PyDict_SetItemString`, `PyMapping_HasKeyString` etc, etc.
  These APIs cause wasteful repeated string conversion.
  If the string you are using is a constant, e.g., `PyDict_GetItemString(dict, "identifier")`, then make an id with `Py_Identifier(identifier)` and then use `_PyDict_GetItemId(&PyId_identifier)`. If the string is not constant, convert it to a Python object with `PyUnicode_FromString()` and then use e.g., `PyDict_GetItem`.

- `PyModule_AddObject`. This steals a reference on success but not on failure and requires unique cleanup code. Instead, use `PyObject_SetAttr`.

(error_handling_macros)=

## Error Handling Macros

The file `error_handling.h` defines several macros to help make error handling as simple and uniform as possible.

### Error Propagation Macros

In a language with exception handling as a feature, error propagation requires no explicit code, it is only if you want to prevent an error from propagating that you use a `try`/`catch` block. On the other hand, in C all error propagation must be done explicitly.

We define macros to help make error propagation look as simple and uniform as possible.
They can only be used in a function with a `finally:` label which should handle resource cleanup for both the success branch and all the failing branches (see structure of functions section below). When compiled with `DEBUG_F`, these commands will write a message to `console.error` reporting the line, function, and file where the error occurred.

- `FAIL()` -- unconditionally `goto finally;`.
- `FAIL_IF_NULL(ptr)` -- `goto finally;` if `ptr == NULL`. This should be used with any function that returns a pointer and follows the standard Python calling convention.
- `FAIL_IF_MINUS_ONE(num)` -- `goto finally;` if `num == -1`. This should be used with any function that returns a number and follows the standard Python calling convention.
- `FAIL_IF_NONZERO(num)` -- `goto finally;` if `num != 0`. Can be used with functions that return any nonzero error code on failure.
- `FAIL_IF_ERR_OCCURRED()` -- `goto finally;` if the Python error indicator is set (in other words if `PyErr_Occurred()`).
- `FAIL_IF_ERR_MATCHES(python_err_type)` -- `goto finally;` if `PyErr_ExceptionMatches(python_err_type)`, for example `FAIL_IF_ERR_MATCHES(PyExc_AttributeError);`

### JavaScript to CPython calling convention adapators

If we call a JavaScript function from C and that JavaScript function throws an error, it is impossible to catch it in C. We define two `EM_JS` adaptors to convert from the JavaScript calling convention to the CPython calling convention. The point of this is to ensure that errors that occur in `EM_JS` functions can be handled in C code using the ` FAIL_*`` macros. When compiled with  `DEBUG_F`, when a JavaScript error is thrown a message will also be written to `console.error`. The wrappers do roughly the following:

```javascript
try {
  // body of function here
} catch (e) {
  // wrap e in a Python exception and set the Python error indicator
  // return error code
}
```

There are two variants: `EM_JS_NUM` returns `-1` as the error code, `EM_JS_REF` returns `NULL == 0` as the error code. A couple of simple examples:
Use `EM_JS_REF` when return value is a `JsRef`:

```javascript
EM_JS_REF(JsRef, hiwire_call, (JsRef idfunc, JsRef idargs), {
  let jsfunc = Module.hiwire.get_value(idfunc);
  let jsargs = Module.hiwire.get_value(idargs);
  return Module.hiwire.new_value(jsfunc(... jsargs));
});
```

Use `EM_JS_REF` when return value is a `PyObject`:

```javascript
EM_JS_REF(PyObject*, __js2python, (JsRef id), {
  // body here
});
```

If the function returns `void`, use `EM_JS_NUM` with return type `errcode`. `errcode` is a typedef for `int`. `EM_JS_NUM` will automatically return `-1` if an error occurs and `0` if not:

```javascript
EM_JS_NUM(errcode, hiwire_set_member_int, (JsRef idobj, int idx, JsRef idval), {
  Module.hiwire.get_value(idobj)[idx] = Module.hiwire.get_value(idval);
});
```

If the function returns `int` or `bool` use `EM_JS_NUM`:

```javascript
EM_JS_NUM(int, hiwire_get_length, (JsRef idobj), {
  return Module.hiwire.get_value(idobj).length;
});
```

These wrappers enable the following sort of code:

```python
try:
  jsfunc()
except JsException:
  print("Caught an exception thrown in JavaScript!")
```

## Structure of functions

In C it takes special care to correctly and cleanly handle both reference counting and exception propagation. In Python (or other higher level languages), all references are released in an implicit finally block at the end of the function. Implicitly, it is as if you wrote:

```python
def f():
  try: # implicit
    a = do_something()
    b = do_something_else()
    c = a + b
    return some_func(c)
  finally:
    # implicit, free references both on successful exit and on exception
    decref(a)
    decref(b)
    decref(c)
```

Freeing all references at the end of the function allows us to separate reference counting boilerplate from the "actual logic" of the function definition. When a function does correct error propogation, there will be many different execution paths, roughly linearly many in the length of the function. For example, the above psuedocode could exit in five different ways: `do_something` could raise an exception, `do_something_else` could raise an exception, `a + b` could raise an exception, `some_func` could raise an exception, or the function could return successfully. (Even a Python function like `def f(a,b,c,d): return (a + b) * c - d` has four execution paths.) The point of the `try`/`finally` block is that we know the resources are freed correctly without checking once for each execution path.

To do this, we divide any function that produces more than a couple of owned `PyObject*`s or `JsRef`s into several "segments".
The more owned references there are in a function and the longer it is, the more important it becomes to follow this style carefully.
By being as consistent as possible, we reduce the burden on people reading the code to double-check that you are not leaking memory or errors. In short functions it is fine to do something ad hoc.

1. The guard block. The first block of a function does sanity checks on the inputs and argument parsing, but only to the extent possible without creating any owned references. If you check more complicated invariants on the inputs in a way that requires creating owned references, this logic belongs in the body block.

Here's an example of a `METH_VARARGS` function:

```C
PyObject*
JsImport_CreateModule(PyObject* self, PyObject* args)
{
  // Guard
  PyObject* name;
  PyObject* jsproxy;
  // PyArg_UnpackTuple uses an unusual calling convention:
  // It returns `false` on failure...
  if (!PyArg_UnpackTuple(args, "create_module", 2, 2, &spec, &jsproxy)) {
    return NULL;
  }
  if (!JsProxy_Check(jsproxy)) {
    PyErr_SetString(PyExc_TypeError, "package is not an instance of jsproxy");
    return NULL;
  }
```

2. Forward declaration of owned references. This starts by declaring a success flag `bool success = false`. This will be used in the finally block to decide whether the finally block was entered after a successful execution or after an error. Then declare every reference counted variable that we will create during execution of the function. Finally, declare the variable that we are planning to return.
   Typically, this will be called `result`, but in this case the function is named `CreateModule` so we name the return variable `module`.

```C
  bool success = false;
  // Note: these are all the objects that we will own. If a function returns
  // a borrow, we XINCREF the result so that we can CLEAR it in the finally block.
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

3. The body of the function. The vast majority of API calls can return error codes. You MUST check every fallible API for an error. Also, as you are writing the code, you should look up every Python API you use that returns a reference to determine whether it returns a borrowed reference or a new one. If it returns a borrowed reference, immediately `Py_XINCREF()` the result to convert it into an owned reference (before `FAIL_IF_NULL`, to be consistent with the case where you use custom error handling).

```C
  name = PyUnicode_FromString(name_utf8);
  FAIL_IF_NULL(name);
  sys_modules = PyImport_GetModuleDict(); // returns borrow
  Py_XINCREF(sys_modules);
  FAIL_IF_NULL(sys_modules);
  module = PyDict_GetItemWithError(sys_modules, name); // returns borrow
  Py_XINCREF(module);
  FAIL_IF_NULL(module);
  if(module && !JsImport_Check(module)){
    PyErr_Format(PyExc_KeyError,
      "Cannot mount with name '%s': there is an existing module by this name that was not mounted with 'pyodide.mountPackage'."
      , name
    );
    FAIL();
  }
// ... [SNIP]
```

4. The `finally` block. Here we will clear all the variables we declared at the top in exactly the same order. Do not clear the arguments! They are borrowed. According to the standard Python function calling convention, they are the responsibility of the calling code.

```C
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

One case where you do need to `Py_CLEAR` a variable in the body of a function is if that variable is allocated in a loop:

```C
  // refcounted variable declarations
  PyObject* pyentry = NULL;
  // ... other stuff
  Py_ssize_t n = PySequence_Length(pylist);
  for (Py_ssize_t i = 0; i < n; i++) {
    pyentry = PySequence_GetItem(pydir, i);
    FAIL_IF_MINUS_ONE(do_something(pyentry));
    Py_CLEAR(pyentry); // important to use Py_CLEAR and not Py_decref.
  }

  success = true
finally:
  // have to clear pyentry at end too in case do_something failed in the loop body
  Py_CLEAR(pyentry);
```

## Testing

Any nonstatic C function called `some_name` defined not using `EM_JS` will be exposed as `pyodide._module._some_name`, and this can be used in tests to good effect. If the arguments / return value are not just numbers and booleans, it may take some effort to set up the function call.

If you want to test an `EM_JS` function, consider moving the body of the function to an API defined on `Module`. You should still wrap the function with `EM_JS_REF` or `EM_JS_NUM` in order to get a function with the CPython calling convention.
