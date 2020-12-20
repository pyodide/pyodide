#include "Python.h"
#include "frameobject.h"

static int interrupt_interval = 10000;
static int interrupt_clock = 0;

static PyObject* interrupt_buffer;

static int
do_interrupt_handling()
{
  Py_AddPendingCall(&do_interrupt_handling, NULL);
  interrupt_clock--;
  if (interrupt_clock > 0) {
    return 0;
  }
  interrupt_clock = interrupt_interval;
  if (interrupt_buffer != Py_None) {
    PyObject* py_value = _PyObject_CallNoArg(interrupt_buffer);
    if (py_value == NULL) {
      goto fail;
    }
    long value = PyLong_AsLong(py_value);
    if (PyErr_Occurred()) {
      Py_CLEAR(py_value);
      goto fail;
    }
    Py_CLEAR(py_value);
    if (value != 0) {
      PyErr_SetInterrupt();
    }
  }
  return 0;

fail:
  Py_DECREF(interrupt_buffer);
  Py_INCREF(Py_None);
  interrupt_buffer = Py_None;
  // Adjust error message?
  // Clear error?
  return -1;
}

PyObject*
pyodide_set_interrupt_buffer(PyObject* self, PyObject* arg)
{
  if (arg != Py_None && PyCallable_Check(arg) == 0) {
    PyErr_SetString(
      PyExc_TypeError,
      "Argument to 'set_interrupt_buffer' must be callable or 'None'");
    return NULL;
  }

  Py_DECREF(interrupt_buffer);
  interrupt_buffer = arg;
  Py_RETURN_NONE;
}

PyDoc_STRVAR(set_interrupt_buffer_doc,
             "set_interrupt_buffer(callback)\n"
             "\n"
             "Periodically polls ``callback``. If ``callback`` returns a "
             "nonzero value, triggers a ``SIGINT`` signal.\n"
             "By default, the signal handler for ``SIGINT`` raises a "
             "``KeyboardException``, but using the ``signals`` package this "
             "can be changed."
             "If ``callback`` returns a value that cannot be interpreted as an "
             "integer or if an exception is triggered inside of ``callback``"
             "then the exception is allowed to propagate but the interrupt "
             "buffer is set to ``None``."
             "If called with ``None``, interrupt polling is turned off."
             "\n"
             "Args:\n"
             "   callback -- a zero argument function which returns an int. If "
             "it returns a nonzero value, triggers ``SIGINT``.\n");

static PyMethodDef set_interrupt_buffer_methoddef = {
  "set_interrupt_buffer",
  pyodide_set_interrupt_buffer,
  METH_O,
  set_interrupt_buffer_doc
};

PyObject*
pyodide_get_interrupt_buffer(PyObject* self, PyObject* _args)
{
  Py_INCREF(interrupt_buffer);
  return interrupt_buffer;
}

PyDoc_STRVAR(get_interrupt_buffer_doc,
             "get_interrupt_buffer()\n"
             "\n"
             "Gets the current interrupt buffer.");

static PyMethodDef get_interrupt_buffer_methoddef = {
  "get_interrupt_buffer",
  pyodide_get_interrupt_buffer,
  METH_NOARGS,
  get_interrupt_buffer_doc
};

PyObject*
pyodide_set_interrupt_interval(PyObject* self, PyObject* arg)
{
  long value = PyLong_AsLong(arg);
  if (PyErr_Occurred()) {
    return NULL;
  }
  interrupt_interval = value;
  Py_RETURN_NONE;
}

PyDoc_STRVAR(set_interrupt_interval_doc,
             "set_interrupt_interval(callback)\n"
             "\n"
             "docstring here....");

static PyMethodDef set_interrupt_interval_methoddef = {
  "set_interrupt_interval",
  pyodide_set_interrupt_interval,
  METH_NOARGS,
  set_interrupt_interval_doc
};

int
interrupts_init()
{
  Py_INCREF(Py_None);
  interrupt_buffer = Py_None;

  // PyEval_SetTrace(trace_trampoline, NULL);

  Py_AddPendingCall(&do_interrupt_handling, NULL);

  PyObject* module = NULL;
  PyObject* name = NULL;
  PyObject* func = NULL;
  PyObject* sigint = NULL;
  PyObject* default_int_handler = NULL;

  Py_CLEAR(module);
  module = PyImport_ImportModule("signal");
  if (module == NULL) {
    goto fail;
  }

  sigint = PyObject_GetAttrString(module, "SIGINT");
  if (sigint == NULL) {
    goto fail;
  }

  default_int_handler = PyObject_GetAttrString(module, "default_int_handler");
  if (default_int_handler == NULL) {
    goto fail;
  }

  PyObject* result =
    PyObject_CallMethod(module, "signal", "OO", sigint, default_int_handler);
  if (result == NULL) {
    goto fail;
  }
  Py_CLEAR(result);

  // Py_CLEAR(module);
  // module = PyImport_ImportModule("sys");
  // if (module == NULL) {
  //   goto fail;
  // }
  // name = PyModule_GetNameObject(module);
  // if (name == NULL) {
  //   goto fail;
  // }

  // func = PyCFunction_NewEx(&settrace_methoddef, (PyObject*)module, name);
  // if (func == NULL) {
  //   goto fail;
  // }
  // if (PyObject_SetAttrString(module, "settrace", func)) {
  //   goto fail;
  // }

  Py_CLEAR(module);
  module = PyImport_ImportModule("pyodide");
  if (module == NULL) {
    goto fail;
  }
  Py_CLEAR(name);
  name = PyModule_GetNameObject(module);
  if (name == NULL) {
    goto fail;
  }

  Py_CLEAR(func);
  func =
    PyCFunction_NewEx(&set_interrupt_buffer_methoddef, (PyObject*)module, name);
  if (func == NULL) {
    goto fail;
  }
  if (PyObject_SetAttrString(module, "set_interrupt_buffer", func)) {
    goto fail;
  }

  Py_CLEAR(func);
  func =
    PyCFunction_NewEx(&get_interrupt_buffer_methoddef, (PyObject*)module, name);
  if (func == NULL) {
    goto fail;
  }
  if (PyObject_SetAttrString(module, "get_interrupt_buffer", func)) {
    goto fail;
  }

  Py_CLEAR(sigint);
  Py_CLEAR(default_int_handler);
  Py_CLEAR(module);
  Py_CLEAR(name);
  Py_CLEAR(func);
  return 0;

fail:
  Py_CLEAR(sigint);
  Py_CLEAR(default_int_handler);
  Py_CLEAR(module);
  Py_CLEAR(name);
  Py_CLEAR(func);
  return -1;
}