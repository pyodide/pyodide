#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "js2python.h"

#include <emscripten.h>

#include "jsproxy.h"
#include "pyproxy.h"

PyObject*
_js2python_allocate_string(int size, int max_code_point)
{
  return PyUnicode_New(size, max_code_point);
}

void*
_js2python_get_ptr(PyObject* obj)
{
  return PyUnicode_DATA(obj);
}

PyObject*
_js2python_number(double val)
{
  double i;

  if (modf(val, &i) == 0.0)
    return PyLong_FromDouble(i);

  return PyFloat_FromDouble(val);
}

PyObject*
_js2python_none()
{
  Py_RETURN_NONE;
}

PyObject*
_js2python_true()
{
  Py_RETURN_TRUE;
}

PyObject*
_js2python_false()
{
  Py_RETURN_FALSE;
}

PyObject*
_js2python_pyproxy(PyObject* val)
{
  Py_INCREF(val);
  return val;
}

PyObject*
_js2python_memoryview(JsRef id)
{
  PyObject* jsproxy = JsProxy_create(id);
  return PyMemoryView_FromObject(jsproxy);
}

EM_JS_REF(PyObject*, js2python, (JsRef id), {
  let value = Module.hiwire.get_value(id);
  let result = Module.__js2python_convertImmutable(value);
  // clang-format off
  if (result !== 0) {
    return result;
  }
  if (value['byteLength'] !== undefined) {
    return __js2python_memoryview(id);
  } else {
    return _JsProxy_create(id);
  }
  // clang-format on
})

EM_JS_REF(PyObject*, js2python_convert, (JsRef id, int depth), {
  return Module.__js2python_convert(id, new Map(), depth);
});

EM_JS_NUM(errcode, js2python_init, (), {
  Module.__js2python_string = function(value)
  {
    // The general idea here is to allocate a Python string and then
    // have Javascript write directly into its buffer.  We first need
    // to determine if is needs to be a 1-, 2- or 4-byte string, since
    // Python handles all 3.
    let max_code_point = 0;
    let length = value.length;
    for (let i = 0; i < value.length; i++) {
      let code_point = value.codePointAt(i);
      max_code_point = Math.max(max_code_point, code_point);
      if (code_point > 0xffff) {
        // If we have a code point requiring UTF-16 surrogate pairs, the
        // number of characters (codePoints) is less than value.length,
        // so skip the next charCode and subtract 1 from the length.
        i++;
        length--;
      }
    }

    let result = __js2python_allocate_string(length, max_code_point);
    // clang-format off
    if (result === 0) {
      // clang-format on
      return 0;
    }

    let ptr = __js2python_get_ptr(result);
    if (max_code_point > 0xffff) {
      ptr = ptr / 4;
      for (let i = 0, j = 0; j < length; i++, j++) {
        let code_point = value.codePointAt(i);
        Module.HEAPU32[ptr + j] = code_point;
        if (code_point > 0xffff) {
          i++;
        }
      }
    } else if (max_code_point > 0xff) {
      ptr = ptr / 2;
      for (let i = 0; i < length; i++) {
        Module.HEAPU16[ptr + i] = value.codePointAt(i);
      }
    } else {
      for (let i = 0; i < length; i++) {
        Module.HEAPU8[ptr + i] = value.codePointAt(i);
      }
    }

    return result;
  };

  Module.__js2python_convertImmutable = function(value)
  {
    let type = typeof value;
    // clang-format off
    if (type === 'string') {
      return Module.__js2python_string(value);
    } else if (type === 'number') {
      return __js2python_number(value);
    } else if (value === undefined || value === null) {
      return __js2python_none();
    } else if (value === true) {
      return __js2python_true();
    } else if (value === false) {
      return __js2python_false();
    } else if (Module.PyProxy.isPyProxy(value)) {
      return __js2python_pyproxy(Module.PyProxy._getPtr(value));
    }
    // clang-format on
    return 0;
  };

  Module.__js2python_convertList = function(obj, map, depth)
  {
    let list = _PyList_New(obj.length);
    // clang-format off
    if (list === 0) {
      // clang-format on
      return 0;
    }
    map.set(obj, list);
    for (let i = 0; i < obj.length; i++) {
      let entryid = Module.hiwire.new_value(obj[i]);
      let item = Module.__js2python_convert(entryid, map, depth);
      Module.hiwire.decref(entryid);
      // clang-format off
      if (item === 0) {
        // clang-format on
        _Py_DecRef(list);
        return 0;
      }
      // PyList_SetItem steals a reference to item no matter what
      let errcode = _PyList_SetItem(list, i, item);
      // clang-format off
      if (errcode === -1) {
        // clang-format on
        _Py_DecRef(list);
        return 0;
      }
    }
    return list;
  };

  Module.__js2python_convertMap = function(obj, entries, map, depth)
  {
    let dict = _PyDict_New();
    // clang-format off
    if (dict === 0) {
      // clang-format on
      return 0;
    }
    map.set(obj, dict);
    for (let[key_js, value_js] of entries) {
      let key_id = Module.hiwire.new_value(key_js);
      let key_py = Module.__js2python_convert(key_id, map, depth);
      Module.hiwire.decref(key_id);
      // clang-format off
      if (key_py === 0) {
        // clang-format on
        _Py_DecRef(dict);
        return 0;
      }

      let value_id = Module.hiwire.new_value(value_js);
      let value_py = Module.__js2python_convert(value_id, map, depth);
      Module.hiwire.decref(value_id);
      // clang-format off
      if (value_py === 0) {
        // clang-format on
        _Py_DecRef(dict);
        return 0;
      }

      // PyDict_SetItem does not steal references
      let errcode = _PyDict_SetItem(dict, key_py, value_py);
      _Py_DecRef(key_py);
      _Py_DecRef(value_py);
      // clang-format off
      if (errcode === -1) {
        // clang-format on
        _Py_DecRef(dict);
        return 0;
      }
    }
    return dict;
  };

  Module.__js2python_convertSet = function(obj, map, depth)
  {
    let set = _PySet_New(0);
    // clang-format off
    if (set === 0) {
      // clang-format on
      return 0;
    }
    map.set(obj, set);
    for (let key_js of obj) {
      let key_id = Module.hiwire.new_value(key_js);
      let key_py = Module.__js2python_convert(key_id, map, depth);
      Module.hiwire.decref(key_id);
      // clang-format off
      if (key_py === 0) {
        // clang-format on
        _Py_DecRef(set);
        return 0;
      }
      let errcode = _PySet_Add(set, key_py);
      _Py_DecRef(key_py);
      // clang-format off
      if (errcode === -1) {
        // clang-format on
        _Py_DecRef(set);
        return 0;
      }
    }
    return set;
  };

  Module.__js2python_convertOther = function(id, value, map, depth)
  {
    let toStringTag = Object.prototype.toString.call(value);
    // clang-format off
    if (Array.isArray(value) || value === "[object HTMLCollection]" ||
                                           value === "[object NodeList]") {
      return Module.__js2python_convertList(value, map, depth);
    }
    if (toStringTag === "[object Map]" || value instanceof Map) {
      return Module.__js2python_convertMap(value, value.entries(), map, depth);
    }
    if (toStringTag === "[object Set]" || value instanceof Set) {
      return Module.__js2python_convertSet(value, map, depth);
    }
    if (toStringTag === "[object Object]" && (value.constructor === undefined || value.constructor.name === "Object")) {
      return Module.__js2python_convertMap(value, Object.entries(value), map, depth);
    }
    // clang-format on
    return _JsProxy_create(id);
  };

  Module.__js2python_convert = function(id, map, depth)
  {
    let value = Module.hiwire.get_value(id);
    let result = Module.__js2python_convertImmutable(value);
    // clang-format off
    if (result !== 0) {
      return result;
    }
    if (depth === 0) {
      return _JsProxy_create(id);
    }
    result = map.get(value);
    if (result !== undefined) {
      return result;
    }
    // clang-format on
    return Module.__js2python_convertOther(id, value, map, depth - 1);
  };

  return 0;
})
