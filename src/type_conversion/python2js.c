#include "python2js.h"

#include <emscripten.h>

#include "hiwire.h"
#include "jsproxy.h"
#include "pyproxy.h"

#include "python2js_buffer.h"

static PyObject* tbmod = NULL;

static int
_python2js_unicode(PyObject* x);

/** Cache a conversion of a python object
 * \param map A python dict
 * \param parent A python object that we have converted
 * \param js
 * 
 */
static int
_python2js_add_to_cache(PyObject* map, PyObject* pyobject, int jsobject);

static int
_python2js_remove_from_cache(PyObject* map, PyObject* pyobject);

static int
_python2js_cache(PyObject* x,
                      PyObject* map,
                      int (*caller)(PyObject*, PyObject*));

int
pythonexc2js()
{
  PyObject* type;
  PyObject* value;
  PyObject* traceback;
  int no_traceback = 0;

  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  int excval = HW_ERROR;
  int exc;

  if (type == NULL || type == Py_None || value == NULL || value == Py_None) {
    excval = hiwire_string_ascii((int)"No exception type or value");
    PyErr_Print();
    PyErr_Clear();
    goto exit;
  }

  if (tbmod == NULL) {
    tbmod = PyImport_ImportModule("traceback");
    if (tbmod == NULL) {
      PyObject* repr = PyObject_Repr(value);
      if (repr == NULL) {
        excval = hiwire_string_ascii((int)"Could not get repr for exception");
      } else {
        excval = _python2js_unicode(repr);
        Py_DECREF(repr);
      }
      goto exit;
    }
  }

  PyObject* format_exception;
  if (traceback == NULL || traceback == Py_None) {
    no_traceback = 1;
    format_exception = PyObject_GetAttrString(tbmod, "format_exception_only");
  } else {
    format_exception = PyObject_GetAttrString(tbmod, "format_exception");
  }
  if (format_exception == NULL) {
    excval =
      hiwire_string_ascii((int)"Could not get format_exception function");
  } else {
    PyObject* pylines;
    if (no_traceback) {
      pylines =
        PyObject_CallFunctionObjArgs(format_exception, type, value, NULL);
    } else {
      pylines = PyObject_CallFunctionObjArgs(
        format_exception, type, value, traceback, NULL);
    }
    if (pylines == NULL) {
      excval =
        hiwire_string_ascii((int)"Error calling traceback.format_exception");
      PyErr_Print();
      PyErr_Clear();
      goto exit;
    } else {
      PyObject* empty = PyUnicode_FromString("");
      PyObject* pystr = PyUnicode_Join(empty, pylines);
      printf("Python exception:\n");
      printf("%s\n", PyUnicode_AsUTF8(pystr));
      excval = _python2js_unicode(pystr);
      Py_DECREF(pystr);
      Py_DECREF(empty);
      Py_DECREF(pylines);
    }
    Py_DECREF(format_exception);
  }

exit:
  PyErr_Clear();
  hiwire_throw_error(excval);
  return HW_ERROR;
}

static int
_python2js_float(PyObject* x)
{
  double x_double = PyFloat_AsDouble(x);
  if (x_double == -1.0 && PyErr_Occurred()) {
    return HW_ERROR;
  }
  return hiwire_double(x_double);
}

static int
_python2js_long(PyObject* x)
{
  int overflow;
  long x_long = PyLong_AsLongAndOverflow(x, &overflow);
  if (x_long == -1) {
    if (overflow) {
      PyObject* py_float = PyNumber_Float(x);
      if (py_float == NULL) {
        return HW_ERROR;
      }
      return _python2js_float(py_float);
    } else if (PyErr_Occurred()) {
      return HW_ERROR;
    }
  }
  return hiwire_int(x_long);
}

static int
_python2js_unicode(PyObject* x)
{
  int kind = PyUnicode_KIND(x);
  int data = (int)PyUnicode_DATA(x);
  int length = (int)PyUnicode_GET_LENGTH(x);
  switch (kind) {
    case PyUnicode_1BYTE_KIND:
      return hiwire_string_ucs1(data, length);
    case PyUnicode_2BYTE_KIND:
      return hiwire_string_ucs2(data, length);
    case PyUnicode_4BYTE_KIND:
      return hiwire_string_ucs4(data, length);
    default:
      PyErr_SetString(PyExc_ValueError, "Unknown Unicode KIND");
      return HW_ERROR;
  }
}

static int
_python2js_bytes(PyObject* x)
{
  char* x_buff;
  Py_ssize_t length;
  if (PyBytes_AsStringAndSize(x, &x_buff, &length)) {
    return HW_ERROR;
  }
  return hiwire_bytes((int)(void*)x_buff, length);
}

static int
_python2js_sequence(PyObject* x,
                         PyObject* map,
                         int (*caller)(PyObject*, PyObject*))
{
  int jsarray = hiwire_array();
  if (_python2js_add_to_cache(map, x, jsarray)) {
    hiwire_decref(jsarray);
    return HW_ERROR;
  }
  size_t length = PySequence_Size(x);
  for (size_t i = 0; i < length; ++i) {
    PyObject* pyitem = PySequence_GetItem(x, i);
    if (pyitem == NULL) {
      // If something goes wrong converting the sequence (as is the case with
      // Pandas data frames), fallback to the Python object proxy
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jsarray);
      PyErr_Clear();
      Py_INCREF(x);
      return get_pyproxy(x);
    }
    int jsitem = _python2js_cache(pyitem, map, caller);
    if (jsitem == HW_ERROR) {
      _python2js_remove_from_cache(map, x);
      Py_DECREF(pyitem);
      hiwire_decref(jsarray);
      return HW_ERROR;
    }
    Py_DECREF(pyitem);
    hiwire_push_array(jsarray, jsitem);
    hiwire_decref(jsitem);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsarray);
    return HW_ERROR;
  }
  return jsarray;
}

static int
_python2js_dict(PyObject* x,
                     PyObject* map,
                     int (*caller)(PyObject*, PyObject*))
{
  int jsdict = hiwire_object();
  if (_python2js_add_to_cache(map, x, jsdict)) {
    hiwire_decref(jsdict);
    return HW_ERROR;
  }
  PyObject *pykey, *pyval;
  Py_ssize_t pos = 0;
  while (PyDict_Next(x, &pos, &pykey, &pyval)) {
    int jskey = _python2js_cache(pykey, map, caller);
    if (jskey == HW_ERROR) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jsdict);
      return HW_ERROR;
    }
    int jsval = _python2js_cache(pyval, map, caller);
    if (jsval == HW_ERROR) {
      _python2js_remove_from_cache(map, x);
      hiwire_decref(jskey);
      hiwire_decref(jsdict);
      return HW_ERROR;
    }
    hiwire_push_object_pair(jsdict, jskey, jsval);
    hiwire_decref(jskey);
    hiwire_decref(jsval);
  }
  if (_python2js_remove_from_cache(map, x)) {
    hiwire_decref(jsdict);
    return HW_ERROR;
  }
  return jsdict;
}

int
python2js_can(PyObject* x)
{
  return PySequence_Check(x) || PyDict_Check(x) || PyObject_CheckBuffer(x);
}

static int 
_python2js_immutable(PyObject* x){
  if (x == Py_None) {
    return hiwire_undefined();
  } else if (x == Py_True) {
    return hiwire_true();
  } else if (x == Py_False) {
    return hiwire_false();
  } else if (PyLong_Check(x)) {
    return _python2js_long(x);
  } else if (PyFloat_Check(x)) {
    return _python2js_float(x);
  } else if (PyUnicode_Check(x)) {
    return _python2js_unicode(x);
  } else if (PyBytes_Check(x)) {
    return _python2js_bytes(x);
  } else {
    return HW_ERROR;
  }
}


#define RET_IF_NOT_ERR(x)   \
  do {                      \
    result = x;             \
    if(result != HW_ERROR){ \
      return result;        \
    }                       \
  } while(0)


static int
_python2js_deep(PyObject* x, PyObject* map)
{
  int result;
  RET_IF_NOT_ERR(_python2js_immutable(x));

  int (*self)(PyObject*, PyObject*) = &_python2js_deep;
  
  if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (PyList_Check(x) || PyTuple_Check(x)) {
    return _python2js_sequence(x, map, self);
  } else if (PyDict_Check(x)) {
    return _python2js_dict(x, map, self);
  }

  RET_IF_NOT_ERR(_python2js_buffer(x));

  if (result != HW_ERROR) {
    return result;
  }

  if (PySequence_Check(x)) {
    return _python2js_sequence(x, map, self);
  }

    return get_pyproxy(x);
  }
}

static int
_python2js_minimal(PyObject* x, PyObject* map)
{
  int result;
  RET_IF_NOT_ERR(_python2js_immutable(x));

  int (*self)(PyObject*, PyObject*) = &_python2js_deep;

  if (JsProxy_Check(x)) {
    return JsProxy_AsJs(x);
  } else if (PyTuple_Check(x)) {
    return _python2js_sequence(x, map, &_python2js_nocopy);
  } else {
    RET_IF_NOT_ERR(_python2js_tryinto_buffer(x));
    // if (PySequence_Check(x)) {
    //   return _python2js_sequence(x, map);
    // }
    return get_pyproxy(x);
  }
}

static int
_python2js_add_to_cache(PyObject* map, PyObject* pyobject, int jsobject)
{
  if(map === NULL){
    return 0;
  }  
  /* Use the pointer converted to an int so cache is by identity, not hash */
  PyObject* pyobjectid = PyLong_FromSize_t((size_t)pyobject);
  PyObject* jsobjectid = PyLong_FromLong(jsobject);
  int result = PyDict_SetItem(map, pyparentid, jsobjectid);
  Py_DECREF(pyparentid);
  Py_DECREF(jsparentid);

  return result ? HW_ERROR : 0;
}

static int
_python2js_remove_from_cache(PyObject* map, PyObject* pyparent)
{
  if(map === NULL){
    return 0;
  }
  PyObject* pyparentid = PyLong_FromSize_t((size_t)pyparent);
  int result = PyDict_DelItem(map, pyparentid);
  Py_DECREF(pyparentid);

  return result ? HW_ERROR : 0;
}

static int
_python2js_cache(PyObject* x,
                      PyObject* map,
                      int (*caller)(PyObject*, PyObject*))
{
  if(map === NULL){
    return 0;
  }  
  PyObject* id = PyLong_FromSize_t((size_t)x);
  PyObject* val = PyDict_GetItem(map, id);
  int result;
  if (val) {
    result = PyLong_AsLong(val);
    if (result != HW_ERROR) {
      result = hiwire_incref(result);
    }
  } else {
    result = caller(x, map);
  }
  Py_DECREF(id);
  return result;
}

int
python2js_nocopy(PyObject* x)
{
  PyObject* map = PyDict_New();
  // This caching is pretty overkill for the no copy version, since it is only
  // for tuples. It is TECHNICALLY possible to have a self-referential tuple:
  // https://stackoverflow.com/questions/11873448/building-self-referencing-tuples
  // This also allows us to share code.
  int result = _python2js_cache(x, map, &_python2js_nocopy);
  Py_DECREF(map);
  if (result == HW_ERROR) {
    return pythonexc2js();
  }
  return result;
}

int
python2js(PyObject* x)
{
  PyObject* map = PyDict_New();
  int result = _python2js_cache(x, map, &_python2js);
  Py_DECREF(map);

  if (result == HW_ERROR) {
    return pythonexc2js();
  }

  return result;
}

int
python2js_init()
{
  return 0;
}
