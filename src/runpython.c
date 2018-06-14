#include "runpython.h"

#include <Python.h>
#include <emscripten.h>
#include <node.h> // from Python

#include "hiwire.h"
#include "python2js.h"

extern PyObject* globals;

static int
is_whitespace(char x)
{
  switch (x) {
    case ' ':
    case '\n':
    case '\r':
    case '\t':
      return 1;
    default:
      return 0;
  }
}

int
_runPython(char* code)
{
  char* last_line = code;
  while (*last_line != 0) {
    ++last_line;
  }
  size_t length = last_line - code;

  PyCompilerFlags cf;
  cf.cf_flags = PyCF_SOURCE_IS_UTF8;
  PyEval_MergeCompilerFlags(&cf);

  if (length == 0) {
    return hiwire_undefined();
  }

  // Find the last non-whitespace-only line since that will provide the result
  // TODO: This way to find the last line will probably break in many ways
  last_line--;
  for (; last_line != code && is_whitespace(*last_line); last_line--) {
  }
  for (; last_line != code && *last_line != '\n'; last_line--) {
  }

  int do_eval_line = 1;
  struct _node* co;
  co = PyParser_SimpleParseStringFlags(last_line, Py_eval_input, cf.cf_flags);
  if (co == NULL) {
    do_eval_line = 0;
    PyErr_Clear();
  }
  PyNode_Free(co);

  PyObject* ret;
  if (do_eval_line == 0 || last_line != code) {
    if (do_eval_line) {
      *last_line = 0;
      last_line++;
    }
    ret = PyRun_StringFlags(code, Py_file_input, globals, globals, &cf);
    if (ret == NULL) {
      return pythonexc2js();
    }
    Py_DECREF(ret);
  }

  switch (do_eval_line) {
    case 0:
      Py_INCREF(Py_None);
      ret = Py_None;
      break;
    case 1:
      ret = PyRun_StringFlags(last_line, Py_eval_input, globals, globals, &cf);
      break;
    case 2:
      ret = PyRun_StringFlags(last_line, Py_file_input, globals, globals, &cf);
      break;
  }

  if (ret == NULL) {
    return pythonexc2js();
  }

  int id = python2js(ret);
  Py_DECREF(ret);
  return id;
}

EM_JS(int, runpython_init, (), {
  Module.runPython = function(code)
  {
    var pycode = allocate(intArrayFromString(code), 'i8', ALLOC_NORMAL);
    var idresult = Module.__runPython(pycode);
    jsresult = Module.hiwire_get_value(idresult);
    Module.hiwire_decref(idresult);
    _free(pycode);
    return jsresult;
  };

  return 0;
});
