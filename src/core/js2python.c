#define PY_SSIZE_T_CLEAN
#include "Python.h"

#include "error_handling.h"
#include "js2python.h"

#include <emscripten.h>

#include "jsmemops.h"
#include "jsproxy.h"
#include "pyproxy.h"

// PyUnicodeDATA is a macro, we need to access it from Javascript
void*
PyUnicode_Data(PyObject* obj)
{
  return PyUnicode_DATA(obj);
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

EM_JS_REF(PyObject*, js2python, (JsRef id), {
  let value = Module.hiwire.get_value(id);
  let result = Module.__js2python_convertImmutable(value);
  // clang-format off
  if (result !== 0) {
    return result;
  }
  return _JsProxy_create(id);
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
    let codepoints = [];
    for (let c of value) {
      codepoints.push(c.codePointAt(0));
    }
    let max_code_point = Math.max(... codepoints);

    let result = _PyUnicode_New(codepoints.length, max_code_point);
    // clang-format off
    if (result === 0) {
      // clang-format on
      return 0;
    }

    let ptr = _PyUnicode_Data(result);
    if (max_code_point > 0xffff) {
      HEAPU32.subarray(ptr / 4, ptr / 4 + codepoints.length).set(codepoints);
    } else if (max_code_point > 0xff) {
      HEAPU16.subarray(ptr / 2, ptr / 2 + codepoints.length).set(codepoints);
    } else {
      HEAPU8.subarray(ptr, ptr + codepoints.length).set(codepoints);
    }

    return result;
  };

  Module.__js2python_bigint = function(value)
  {
    let value_orig = value;
    let length = 0;
    if (value < 0) {
      value = -value;
    }
    while (value) {
      length++;
      value >>= BigInt(32);
    }
    let stackTop = stackSave();
    let ptr = stackAlloc(length * 4);
    value = value_orig;
    for (let i = 0; i < length; i++) {
      DEREF_U32(ptr, i) = Number(value & BigInt(0xffffffff));
      value >>= BigInt(32);
    }
    let result = __PyLong_FromByteArray(ptr,
                                        length * 4 /* length in bytes */,
                                        true /* little endian */,
                                        true /* signed? */);
    stackRestore(stackTop);
    return result;
  };

  Module.__js2python_convertImmutable = function(value)
  {
    let type = typeof value;
    // clang-format off
    if (type === 'string') {
      return Module.__js2python_string(value);
    } else if (type === 'number') {
      if(Number.isSafeInteger(value)){
        return _PyLong_FromDouble(value);
      } else {
        return _PyFloat_FromDouble(value);
      }
    } else if(type === "bigint"){
      return Module.__js2python_bigint(value);
    } else if (value === undefined || value === null) {
      return __js2python_none();
    } else if (value === true) {
      return __js2python_true();
    } else if (value === false) {
      return __js2python_false();
    } else if (Module.isPyProxy(value)) {
      return __js2python_pyproxy(Module.PyProxy_getPtr(value));
    }
    // clang-format on
    return 0;
  };

  class TempError extends Error
  {};

  Module.__js2python_convertList = function(obj, cache, depth)
  {
    let list = _PyList_New(obj.length);
    // clang-format off
    if (list === 0) {
      // clang-format on
      return 0;
    }
    let entryid = 0;
    let item = 0;
    try {
      cache.set(obj, list);
      for (let i = 0; i < obj.length; i++) {
        entryid = Module.hiwire.new_value(obj[i]);
        item = Module.__js2python_convert(entryid, cache, depth);
        // clang-format off
        if (item === 0) {
          // clang-format on
          throw new TempError();
        }
        // clang-format off
        // PyList_SetItem steals a reference to item no matter what
        _Py_IncRef(item);
        if (_PyList_SetItem(list, i, item) === -1) {
          // clang-format on
          throw new TempError();
        }
        Module.hiwire.decref(entryid);
        entryid = 0;
        _Py_DecRef(item);
        item = 0;
      }
    } catch (e) {
      Module.hiwire.decref(entryid);
      _Py_DecRef(item);
      _Py_DecRef(list);
      if (e instanceof TempError) {
        return 0;
      } else if (_PyErr_Occurred()) {
        return 0;
      } else {
        throw e;
      }
    }

    return list;
  };

  Module.__js2python_convertMap = function(obj, entries, cache, depth)
  {
    let dict = _PyDict_New();
    // clang-format off
    if (dict === 0) {
      // clang-format on
      return 0;
    }
    let key_py = 0;
    let value_id = 0;
    let value_py = 0;
    try {
      cache.set(obj, dict);
      for (let[key_js, value_js] of entries) {
        key_py = Module.__js2python_convertImmutable(key_js);
        // clang-format off
        if (key_py === 0) {
          // clang-format on
          if (_PyErr_Occurred()) {
            throw new TempError();
          } else {
            let key_type =
              (key_js.constructor && key_js.constructor.name) || typeof(key_js);
            // clang-format off
            throw new Error(`Cannot use key of type ${key_type} as a key to a Python dict`);
            // clang-format on
          }
        }
        value_id = Module.hiwire.new_value(value_js);
        value_py = Module.__js2python_convert(value_id, cache, depth);
        // clang-format off
        if (value_py === 0) {
          // clang-format on
          throw new TempError();
        }

        // clang-format off
        if (_PyDict_SetItem(dict, key_py, value_py) === -1) {
          // clang-format on
          throw new TempError();
        }
        _Py_DecRef(key_py);
        key_py = 0;
        Module.hiwire.decref(value_id);
        value_id = 0;
        _Py_DecRef(value_py);
        value_py = 0;
      }
    } catch (e) {
      _Py_DecRef(key_py);
      Module.hiwire.decref(value_id);
      _Py_DecRef(value_py);
      _Py_DecRef(dict);
      if (e instanceof TempError) {
        return 0;
      } else if (_PyErr_Occurred()) {
        return 0;
      } else {
        throw e;
      }
    }
    return dict;
  };

  Module.__js2python_convertSet = function(obj, cache, depth)
  {
    let set = _PySet_New(0);
    // clang-format off
    if (set === 0) {
      // clang-format on
      return 0;
    }
    let key_py = 0;
    try {
      cache.set(obj, set);
      for (let key_js of obj) {
        key_py = Module.__js2python_convertImmutable(key_js);
        // clang-format off
        if (key_py === 0) {
          // clang-format on
          if (_PyErr_Occurred()) {
            throw new TempError();
          } else {
            let key_type =
              (key_js.constructor && key_js.constructor.name) || typeof(key_js);
            // clang-format off
            throw new Error(`Cannot use key of type ${key_type} as a key to a Python set`);
            // clang-format on
          }
        }
        let errcode = _PySet_Add(set, key_py);
        // clang-format off
        if (errcode === -1) {
          // clang-format on
          throw new TempError();
        }
        _Py_DecRef(key_py);
        key_py = 0;
      }
    } catch (e) {
      _Py_DecRef(key_py);
      _Py_DecRef(set);
      if (e instanceof TempError) {
        return 0;
      } else if (_PyErr_Occurred()) {
        return 0;
      } else {
        throw e;
      }
    }
    return set;
  };

  function checkBoolIntCollision(obj, ty)
  {
    if (obj.has(1) && obj.has(true)) {
      throw new Error(`Cannot faithfully convert ${
                        ty } into Python since it ` +
                      "contains both 1 and true as keys.");
    }
    if (obj.has(0) && obj.has(false)) {
      throw new Error(`Cannot faithfully convert ${
                        ty } into Python since it ` +
                      "contains both 0 and false as keys.");
    }
  }

  Module.__js2python_convertOther = function(id, value, cache, depth)
  {
    let toStringTag = Object.prototype.toString.call(value);
    // clang-format off
    if (Array.isArray(value) || value === "[object HTMLCollection]" ||
                                           value === "[object NodeList]") {
      return Module.__js2python_convertList(value, cache, depth);
    }
    if (toStringTag === "[object Map]" || value instanceof Map) {
      checkBoolIntCollision(value, "Map");
      return Module.__js2python_convertMap(value, value.entries(), cache, depth);
    }
    if (toStringTag === "[object Set]" || value instanceof Set) {
      checkBoolIntCollision(value, "Set");
      return Module.__js2python_convertSet(value, cache, depth);
    }
    if (toStringTag === "[object Object]" && (value.constructor === undefined || value.constructor.name === "Object")) {
      return Module.__js2python_convertMap(value, Object.entries(value), cache, depth);
    }
    if (toStringTag === "[object ArrayBuffer]" || ArrayBuffer.isView(value)){
      let [format_utf8, itemsize] = Module.get_buffer_datatype(value);
      return _JsBuffer_CloneIntoPython(id, value.byteLength, format_utf8, itemsize);
    }
    // clang-format on
    return _JsProxy_create(id);
  };

  Module.__js2python_convert = function(id, cache, depth)
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
    result = cache.get(value);
    if (result !== undefined) {
      return result;
    }
    // clang-format on
    return Module.__js2python_convertOther(id, value, cache, depth - 1);
  };

  return 0;
})
