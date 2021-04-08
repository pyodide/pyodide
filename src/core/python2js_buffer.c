#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "python2js_buffer.h"
#include "types.h"

#include <endian.h>
#include <stdint.h>

#include "hiwire.h"

// This file handles the conversion of Python buffer objects (which loosely
// represent Numpy arrays) to Javascript.
// Converts everything to nested Javascript arrays, where the scalars are
// standard Javascript numbers (python2js_buffer_recursive)

// clang-format off
EM_JS_REF(JsRef, _python2js_buffer_inner, (
  void* buf,
  Py_ssize_t itemsize,
  int ndim,
  char* format,
  Py_ssize_t* shape,
  Py_ssize_t* strides,
  Py_ssize_t* suboffsets
), {
  // get_converter and _python2js_buffer_recursive defined in python2js_buffer.js
  let converter = Module.get_converter(format, itemsize);
  let result = Module._python2js_buffer_recursive(buf, 0, {
    ndim,
    format,
    itemsize,
    shape,
    strides,
    suboffsets,
    converter,
  });
  return Module.hiwire.new_value(result);
});
// clang-format on

JsRef
_python2js_buffer(PyObject* x)
{
  Py_buffer view;
  if (PyObject_GetBuffer(x, &view, PyBUF_FULL_RO) == -1) {
    return NULL;
  }
  // clang-format off
  JsRef result = _python2js_buffer_inner(
    view.buf,
    view.itemsize,
    view.ndim,
    view.format,
    view.shape,
    view.strides,
    view.suboffsets
  );
  // clang-format on
  PyBuffer_Release(&view);
  return result;
}

#include "include_js_file.h"
#include "python2js_buffer.js"
