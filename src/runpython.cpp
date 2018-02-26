#include "runpython.hpp"

#include <codecvt>
#include <locale>

#include <Python.h>
#include <node.h> // from Python

#include "pylocals.hpp"
#include "python2js.hpp"

using emscripten::val;

static bool is_whitespace(char x) {
  switch (x) {
  case ' ':
  case '\n':
  case '\r':
  case '\t':
    return true;
  default:
    return false;
  }
}

val runPython(std::wstring code) {
  std::wstring_convert<std::codecvt_utf8<wchar_t>> conv;
  std::string code_utf8 = conv.to_bytes(code);
  std::string::iterator last_line = code_utf8.end();

  PyCompilerFlags cf;
  cf.cf_flags = PyCF_SOURCE_IS_UTF8;
  PyEval_MergeCompilerFlags(&cf);

  if (code_utf8.size() == 0) {
    return pythonToJs(Py_None);
  }

  // Find the last non-whitespace-only line since that will provide the result
  // TODO: This way to find the last line will probably break in many ways
  last_line--;
  for (; last_line != code_utf8.begin() && is_whitespace(*last_line); last_line--) {}
  for (; last_line != code_utf8.begin() && *last_line != '\n'; last_line--) {}

  int do_eval_line = 1;
  _node *co;
  co = PyParser_SimpleParseStringFlags(&*last_line, Py_eval_input, cf.cf_flags);
  if (co == NULL) {
    do_eval_line = 0;
    PyErr_Clear();
  }
  PyNode_Free(co);

  PyObject *ret;
  if (do_eval_line == 0 || last_line != code_utf8.begin()) {
    if (do_eval_line) {
      *last_line = 0;
      last_line++;
    }
    ret = PyRun_StringFlags(&*code_utf8.begin(), Py_file_input, globals, locals, &cf);
    if (ret == NULL) {
      return pythonExcToJs();
    }
    Py_DECREF(ret);
  }

  switch (do_eval_line) {
  case 0:
    Py_INCREF(Py_None);
    ret = Py_None;
    break;
  case 1:
    ret = PyRun_StringFlags(&*last_line, Py_eval_input, globals, locals, &cf);
    break;
  case 2:
    ret = PyRun_StringFlags(&*last_line, Py_file_input, globals, locals, &cf);
    break;
  }

  if (ret == NULL) {
    return pythonExcToJs();
  }

  // Now copy all the variables over to the Javascript side
  {
    val js_globals = val::global("window");
    PyObject *k, *v;
    Py_ssize_t pos = 0;

    while (PyDict_Next(globals, &pos, &k, &v)) {
      if (!PyDict_Contains(original_globals, k)) {
        js_globals.set(pythonToJs(k), pythonToJs(v));
      }
    }
  }

  val result = pythonToJs(ret);
  Py_DECREF(ret);
  return result;
}
