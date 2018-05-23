#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

int pyproxy_has(int obj, int idx) {
  PyObject *x = (PyObject *)obj;
  PyObject *pyidx = jsToPython(idx);
  int result = PyObject_HasAttr(x, pyidx) ? hiwire_create_true(): hiwire_create_false();
  Py_DECREF(pyidx);
  return result;
}

int pyproxy_get(int obj, int idx) {
  PyObject *x = (PyObject *)obj;
  PyObject *pyidx = jsToPython(idx);
  PyObject *attr = PyObject_GetAttr(x, pyidx);
  Py_DECREF(pyidx);
  if (attr == NULL) {
    PyErr_Clear();
    return hiwire_create_undefined();
  }

  int ret = pythonToJs(attr);
  Py_DECREF(attr);
  return ret;
};

int pyproxy_set(int obj, int idx, int value) {
  PyObject *x = (PyObject *)obj;
  PyObject *pyidx = jsToPython(idx);
  PyObject *pyvalue = jsToPython(value);
  int ret = PyObject_SetAttr(x, pyidx, pyvalue);
  Py_DECREF(pyidx);
  Py_DECREF(pyvalue);

  if (ret) {
    return pythonExcToJs();
  }
  return value;
}

int pyproxy_deleteProperty(int obj, int idx) {
  PyObject *x = (PyObject *)obj;
  PyObject *pyidx = jsToPython(idx);

  int ret = PyObject_DelAttr(x, pyidx);
  Py_DECREF(pyidx);

  if (ret) {
    return pythonExcToJs();
  }

  return hiwire_create_undefined();
}

int pyproxy_ownKeys(int obj) {
  PyObject *x = (PyObject *)obj;
  PyObject *dir = PyObject_Dir(x);
  if (dir == NULL) {
    return pythonExcToJs();
  }

  int result = hiwire_create_array();
  Py_ssize_t n = PyList_Size(dir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject *entry = PyList_GetItem(dir, i);
    int jsentry = pythonToJs(entry);
    hiwire_push_array(result, jsentry);
    hiwire_decref(jsentry);
  }
  Py_DECREF(dir);

  return result;
}

int pyproxy_enumerate(int obj) {
  return pyproxy_ownKeys(obj);
}

int pyproxy_apply(int obj, int args) {
  PyObject *x = (PyObject *)obj;
  Py_ssize_t length = hiwire_length(args);
  PyObject *pyargs = PyTuple_New(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    int item = hiwire_get_member_int(args, i);
    PyObject *pyitem = jsToPython(item);
    PyTuple_SET_ITEM(pyargs, i, pyitem);
    hiwire_decref(item);
  }
  PyObject *result = PyObject_Call(x, pyargs, NULL);
  if (result == NULL) {
    Py_DECREF(pyargs);
    return pythonExcToJs();
  }
  int jsresult = pythonToJs(result);
  Py_DECREF(result);
  Py_DECREF(pyargs);
  return jsresult;
}

EM_JS(int, pyproxy_new, (int id), {
  var target = function() {};
  target['$$'] = id;
  return Module.hiwire_create_value(new Proxy(target, Module.PyProxy));
});

EM_JS(int, PyProxy_Ready, (), {
  Module.PyProxy = {
    isExtensible: function() { return true },
    has: function (obj, idx) {
      obj = obj['$$'];
      var idxid = Module.hiwire_create_value(idx);
      var result = _pyproxy_has(obj, idxid) != 0;
      Module.hiwire_decref(idxid);
      return result;
    },
    get: function (obj, idx) {
      if (idx === 'toString') {
        return function() {
          // TODO: Cache repr
          var repr = pyodide.pyimport('repr');
          return repr(obj);
        }
      } else if (idx === '$$') {
        return obj['$$'];
      }
      obj = obj['$$'];
      var idxid = Module.hiwire_create_value(idx);
      var resultid = _pyproxy_get(obj, idxid);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(idxid);
      Module.hiwire_decref(resultid);
      return result;
    },
    set: function (obj, idx, value) {
      obj = obj['$$'];
      var idxid = Module.hiwire_create_value(idx);
      var valueid = Module.hiwire_create_value(value);
      var resultid = _pyproxy_set(obj, idxid, valueid);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(idxid);
      Module.hiwire_decref(valueid);
      Module.hiwire_decref(resultid);
      return result;
    },
    deleteProperty: function (obj, idx) {
      obj = obj['$$'];
      var idxid = Module.hiwire_create_value(idx);
      var resultid = _pyproxy_deleteProperty(obj, idxid);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(resultid);
      Module.hiwire_decref(idxid);
      return result;
    },
    ownKeys: function (obj) {
      obj = obj['$$'];
      var resultid = _pyproxy_ownKeys(obj);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(resultid);
      result.push('toString');
      result.push('prototype');
      return result;
    },
    enumerate: function (obj) {
      obj = obj['$$'];
      var resultid = _pyproxy_enumerate(obj);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(resultid);
      result.push('toString');
      result.push('prototype');
      return result;
    },
    apply: function (obj, thisArg, args) {
      obj = obj['$$'];
      var argsid = Module.hiwire_create_value(args);
      var resultid = _pyproxy_apply(obj, argsid);
      var result = Module.hiwire_get_value(resultid);
      Module.hiwire_decref(resultid);
      Module.hiwire_decref(argsid);
      return result;
    },
  };

  return 0;
});
