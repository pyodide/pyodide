#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "docstring.h"
#include "js2python.h"
#include "python2js.h"
#include <emscripten.h>

EM_JS(JsRef, run_js_inner, (JsRef code), {
  const code_str = Hiwire.get_value(code);
  return Hiwire.new_value(eval(code_str));
})

static PyObject*
run_js(PyObject* _mod, PyObject* code)
{
  JsRef code_js = NULL;
  JsRef result_js = NULL;
  PyObject* result_py = NULL;

  if (!PyUnicode_Check(code)) {
    PyErr_Format(PyExc_TypeError,
                 "'code' argument should be a string not '%s'",
                 Py_TYPE(code)->tp_name);
    FAIL();
  }

  code_js = python2js(code);
  FAIL_IF_NULL(code_js);
  result_js = run_js_inner(code_js);
  FAIL_IF_NULL(result_js);
  result_py = js2python(result_js);
  FAIL_IF_NULL(result_py);

finally:
  hiwire_decref(code_js);
  hiwire_decref(result_js);

  return result_py;
}

static PyMethodDef methods[] = {
  {
    "run_js",
    run_js,
    METH_O,
  },
  { NULL } /* Sentinel */
};

int
run_js_init(PyObject* core)
{
  bool success = false;

  PyObject* docstring_source = PyImport_ImportModule("_pyodide._core_docs");
  FAIL_IF_NULL(docstring_source);
  FAIL_IF_MINUS_ONE(
    add_methods_and_set_docstrings(core, methods, docstring_source));

  success = true;
finally:
  Py_CLEAR(docstring_source);
  return success ? 0 : -1;
}
