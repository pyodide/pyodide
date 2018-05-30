#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

int pyproxy_has(int ptrobj, int idkey) {
  PyObject *pyobj = (PyObject *)ptrobj;
  PyObject *pykey = jsToPython(idkey);
  int result = PyObject_HasAttr(pyobj, pykey) ? hiwire_true(): hiwire_false();
  Py_DECREF(pykey);
  return result;
}

int pyproxy_get(int ptrobj, int idkey) {
  PyObject *pyobj = (PyObject *)ptrobj;
  PyObject *pykey = jsToPython(idkey);
  PyObject *pyattr = PyObject_GetAttr(pyobj, pykey);
  Py_DECREF(pykey);
  if (pyattr == NULL) {
    PyErr_Clear();
    return hiwire_undefined();
  }

  int idattr = pythonToJs(pyattr);
  Py_DECREF(pyattr);
  return idattr;
};

int pyproxy_set(int ptrobj, int idkey, int idval) {
  PyObject *pyobj = (PyObject *)ptrobj;
  PyObject *pykey = jsToPython(idkey);
  PyObject *pyval = jsToPython(idval);
  int result = PyObject_SetAttr(pyobj, pykey, pyval);
  Py_DECREF(pykey);
  Py_DECREF(pyval);

  if (result) {
    return pythonExcToJs();
  }
  return idval;
}

int pyproxy_deleteProperty(int ptrobj, int idkey) {
  PyObject *pyobj = (PyObject *)ptrobj;
  PyObject *pykey = jsToPython(idkey);

  int ret = PyObject_DelAttr(pyobj, pykey);
  Py_DECREF(pykey);

  if (ret) {
    return pythonExcToJs();
  }

  return hiwire_undefined();
}

int pyproxy_ownKeys(int ptrobj) {
  PyObject *pyobj = (PyObject *)ptrobj;
  PyObject *pydir = PyObject_Dir(pyobj);

  if (pydir == NULL) {
    return pythonExcToJs();
  }

  int iddir = hiwire_array();
  Py_ssize_t n = PyList_Size(pydir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject *pyentry = PyList_GetItem(pydir, i);
    int identry = pythonToJs(pyentry);
    hiwire_push_array(iddir, identry);
    hiwire_decref(identry);
  }
  Py_DECREF(pydir);

  return iddir;
}

int pyproxy_enumerate(int ptrobj) {
  return pyproxy_ownKeys(ptrobj);
}

int pyproxy_apply(int ptrobj, int idargs) {
  PyObject *pyobj = (PyObject *)ptrobj;
  Py_ssize_t length = hiwire_get_length(idargs);
  PyObject *pyargs = PyTuple_New(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    int iditem = hiwire_get_member_int(idargs, i);
    PyObject *pyitem = jsToPython(iditem);
    PyTuple_SET_ITEM(pyargs, i, pyitem);
    hiwire_decref(iditem);
  }
  PyObject *pyresult = PyObject_Call(pyobj, pyargs, NULL);
  if (pyresult == NULL) {
    Py_DECREF(pyargs);
    return pythonExcToJs();
  }
  int idresult = pythonToJs(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
  return idresult;
}

EM_JS(int, pyproxy_new, (int ptrobj), {
  var target = function() {};
  target['$$'] = ptrobj;
  return Module.hiwire_new_value(new Proxy(target, Module.PyProxy));
});

EM_JS(int, PyProxy_Ready, (), {
  Module.PyProxy = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      ptrobj = jsobj['$$'];
      var idkey = Module.hiwire_new_value(jskey);
      var result = _pyproxy_has(ptrobj, idkey) != 0;
      Module.hiwire_decref(idkey);
      return result;
    },
    get: function (jsobj, jskey) {
      if (jskey === 'toString') {
        return function() {
          // TODO: Cache repr
          var repr = pyodide.pyimport('repr');
          return repr(jsobj);
        }
      } else if (jskey === '$$') {
        return jsobj['$$'];
      }
      ptrobj = jsobj['$$'];
      var idkey = Module.hiwire_new_value(jskey);
      var idresult = _pyproxy_get(ptrobj, idkey);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    set: function (jsobj, jskey, jsval) {
      ptrobj = jsobj['$$'];
      var idkey = Module.hiwire_new_value(jskey);
      var idval = Module.hiwire_new_value(jsval);
      var idresult = _pyproxy_set(ptrobj, idkey, idval);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idval);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    deleteProperty: function (jsobj, jskey) {
      ptrobj = jsobj['$$'];
      var idkey = Module.hiwire_new_value(jskey);
      var idresult = _pyproxy_deleteProperty(ptrobj, idkey);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idkey);
      return jsresult;
    },
    ownKeys: function (jsobj) {
      ptrobj = jsobj['$$'];
      var idresult = _pyproxy_ownKeys(ptrobj);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      jsresult.push('toString');
      jsresult.push('prototype');
      return jsresult;
    },
    enumerate: function (jsobj) {
      ptrobj = jsobj['$$'];
      var idresult = _pyproxy_enumerate(ptrobj);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      jsresult.push('toString');
      jsresult.push('prototype');
      return jsresult;
    },
    apply: function (jsobj, jsthis, jsargs) {
      ptrobj = jsobj['$$'];
      var idargs = Module.hiwire_new_value(jsargs);
      var idresult = _pyproxy_apply(ptrobj, idargs);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idargs);
      return jsresult;
    },
  };

  return 0;
});
