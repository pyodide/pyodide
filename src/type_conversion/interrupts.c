#include "Python.h"
#include "frameobject.h"

static int interrupt_interval = 10000;
static int interrupt_clock = 0;

static PyObject* interrupt_buffer;

static int
do_interrupt_handling()
{
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

// Copied from sysmodule
// https://github.com/python/cpython/blob/v3.8.2/Python/sysmodule.c#L807
// up to line 919.

/*
 * Cached interned string objects used for calling the profile and
 * trace functions.  Initialized by trace_init().
 */
static PyObject* whatstrings[8] = { NULL, NULL, NULL, NULL,
                                    NULL, NULL, NULL, NULL };

static int
trace_init(void)
{
  static const char* const whatnames[8] = { "call",     "exception",
                                            "line",     "return",
                                            "c_call",   "c_exception",
                                            "c_return", "opcode" };
  PyObject* name;
  int i;
  for (i = 0; i < 8; ++i) {
    if (whatstrings[i] == NULL) {
      name = PyUnicode_InternFromString(whatnames[i]);
      if (name == NULL)
        return -1;
      whatstrings[i] = name;
    }
  }
  return 0;
}

static PyObject*
call_trampoline(PyObject* callback,
                PyFrameObject* frame,
                int what,
                PyObject* arg)
{
  PyObject* result;
  PyObject* stack[3];

  if (PyFrame_FastToLocalsWithError(frame) < 0) {
    return NULL;
  }

  stack[0] = (PyObject*)frame;
  stack[1] = whatstrings[what];
  stack[2] = (arg != NULL) ? arg : Py_None;

  /* call the Python-level function */
  result = _PyObject_FastCall(callback, stack, 3);

  PyFrame_LocalsToFast(frame, 1);
  if (result == NULL) {
    PyTraceBack_Here(frame);
  }

  return result;
}

static int
trace_trampoline(PyObject* self, PyFrameObject* frame, int what, PyObject* arg)
{
  if (do_interrupt_handling()) {
    return -1;
  }
  if (self == NULL) {
    return 0;
  }

  PyObject* callback;
  PyObject* result;

  if (what == PyTrace_CALL)
    callback = self;
  else
    callback = frame->f_trace;
  if (callback == NULL)
    return 0;
  result = call_trampoline(callback, frame, what, arg);
  if (result == NULL) {
    PyEval_SetTrace(trace_trampoline, NULL);
    Py_CLEAR(frame->f_trace);
    return -1;
  }
  if (result != Py_None) {
    Py_XSETREF(frame->f_trace, result);
  } else {
    Py_DECREF(result);
  }
  return 0;
}

static PyObject*
replacement_sys_settrace(PyObject* self, PyObject* args)
{
  if (trace_init() == -1)
    return NULL;
  if (args == Py_None)
    PyEval_SetTrace(trace_trampoline, NULL);
  else
    PyEval_SetTrace(trace_trampoline, args);
  Py_RETURN_NONE;
}

PyDoc_STRVAR(
  settrace_doc,
  "settrace(function)\n"
  "\n"
  "Set the global debug tracing function.  It will be called on each\n"
  "function call.  See the debugger chapter in the library manual.");

static PyMethodDef settrace_methoddef = { "settrace",
                                          replacement_sys_settrace,
                                          METH_O,
                                          settrace_doc };

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

  PyEval_SetTrace(trace_trampoline, NULL);

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

  Py_CLEAR(module);
  module = PyImport_ImportModule("sys");
  if (module == NULL) {
    goto fail;
  }
  name = PyModule_GetNameObject(module);
  if (name == NULL) {
    goto fail;
  }

  func = PyCFunction_NewEx(&settrace_methoddef, (PyObject*)module, name);
  if (func == NULL) {
    goto fail;
  }
  if (PyObject_SetAttrString(module, "settrace", func)) {
    goto fail;
  }

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