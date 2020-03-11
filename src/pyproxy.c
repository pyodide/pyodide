#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

int
_pyproxy_has(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  int result = PyObject_HasAttr(pyobj, pykey) ? hiwire_true() : hiwire_false();
  Py_DECREF(pykey);
  return result;
}

int
_pyproxy_get(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* pyattr = PyObject_GetAttr(pyobj, pykey);
  Py_DECREF(pykey);
  if (pyattr == NULL) {
    PyErr_Clear();
    return hiwire_undefined();
  }

  int idattr = python2js(pyattr);
  Py_DECREF(pyattr);
  return idattr;
};

int
_pyproxy_set(int ptrobj, int idkey, int idval)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* pyval = js2python(idval);
  int result = PyObject_SetAttr(pyobj, pykey, pyval);
  Py_DECREF(pykey);
  Py_DECREF(pyval);

  if (result) {
    return pythonexc2js();
  }
  return idval;
}

int
_pyproxy_deleteProperty(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);

  int ret = PyObject_DelAttr(pyobj, pykey);
  Py_DECREF(pykey);

  if (ret) {
    return pythonexc2js();
  }

  return hiwire_undefined();
}

int
_pyproxy_ownKeys(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pydir = PyObject_Dir(pyobj);

  if (pydir == NULL) {
    return pythonexc2js();
  }

  int iddir = hiwire_array();
  Py_ssize_t n = PyList_Size(pydir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject* pyentry = PyList_GetItem(pydir, i);
    int identry = python2js(pyentry);
    hiwire_push_array(iddir, identry);
    hiwire_decref(identry);
  }
  Py_DECREF(pydir);

  return iddir;
}

int
_pyproxy_enumerate(int ptrobj)
{
  return _pyproxy_ownKeys(ptrobj);
}

int
_pyproxy_apply(int ptrobj, int idargs)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_ssize_t length = hiwire_get_length(idargs);
  PyObject* pyargs = PyTuple_New(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    int iditem = hiwire_get_member_int(idargs, i);
    PyObject* pyitem = js2python(iditem);
    PyTuple_SET_ITEM(pyargs, i, pyitem);
    hiwire_decref(iditem);
  }
  PyObject* pyresult = PyObject_Call(pyobj, pyargs, NULL);
  if (pyresult == NULL) {
    Py_DECREF(pyargs);
    return pythonexc2js();
  }
  int idresult = python2js(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
  return idresult;
}

void
_pyproxy_destroy(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_DECREF(ptrobj);
  EM_ASM(delete Module.PyProxies[ptrobj];);
}

EM_JS(int, pyproxy_new, (int ptrobj), {
  // Proxies we've already created are just returned again, so that the
  // same object on the Python side is always the same object on the
  // Javascript side.

  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.
  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire_new_value(Module.PyProxies[ptrobj]);
  }

  var target = function(){};
  target['$$'] = { ptr : ptrobj, type : 'PyProxy' };
  var proxy = new Proxy(target, Module.PyProxy);
  Module.PyProxies[ptrobj] = proxy;

  return Module.hiwire_new_value(proxy);
});

EM_JS(int, pyproxy_init, (), {
  // clang-format off
  Module.PyProxies = {};
  Module.PyProxy = {
    getPtr: function(jsobj) {
      var ptr = jsobj['$$']['ptr'];
      if (ptr === null) {
        throw new Error("Object has already been destroyed");
      }
      return ptr;
    },
    isPyProxy: function(jsobj) {
      return jsobj['$$'] !== undefined && jsobj['$$']['type'] === 'PyProxy';
    },
    addExtraKeys: function(result) {
      result.push('toString');
      result.push('prototype');
      result.push('arguments');
      result.push('caller');
    },
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      ptrobj = this.getPtr(jsobj);
      var idkey = Module.hiwire_new_value(jskey);
      var result = __pyproxy_has(ptrobj, idkey) != 0;
      Module.hiwire_decref(idkey);
      return result;
    },
    get: function (jsobj, jskey) {
      ptrobj = this.getPtr(jsobj);
      if (jskey === 'toString') {
        return function() {
          if (self.pyodide.repr === undefined) {
            self.pyodide.repr = self.pyodide.pyimport('repr');
          }
          return self.pyodide.repr(jsobj);
        }
      } else if (jskey === '$$') {
        return jsobj['$$'];
      } else if (jskey === 'destroy') {
        return function() {
          __pyproxy_destroy(ptrobj);
          jsobj['$$']['ptr'] = null;
        }
      } else if (jskey == 'apply') {
        return function(jsthis, jsargs) {
          var idargs = Module.hiwire_new_value(jsargs);
          var idresult = __pyproxy_apply(ptrobj, idargs);
          var jsresult = Module.hiwire_get_value(idresult);
          Module.hiwire_decref(idresult);
          Module.hiwire_decref(idargs);
          return jsresult;
        };
      }
      var idkey = Module.hiwire_new_value(jskey);
      var idresult = __pyproxy_get(ptrobj, idkey);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    set: function (jsobj, jskey, jsval) {
      ptrobj = this.getPtr(jsobj);
      var idkey = Module.hiwire_new_value(jskey);
      var idval = Module.hiwire_new_value(jsval);
      var idresult = __pyproxy_set(ptrobj, idkey, idval);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idval);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    deleteProperty: function (jsobj, jskey) {
      ptrobj = this.getPtr(jsobj);
      var idkey = Module.hiwire_new_value(jskey);
      var idresult = __pyproxy_deleteProperty(ptrobj, idkey);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idkey);
      return jsresult;
    },
    ownKeys: function (jsobj) {
      ptrobj = this.getPtr(jsobj);
      var idresult = __pyproxy_ownKeys(ptrobj);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    enumerate: function (jsobj) {
      ptrobj = this.getPtr(jsobj);
      var idresult = __pyproxy_enumerate(ptrobj);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    apply: function (jsobj, jsthis, jsargs) {
      ptrobj = this.getPtr(jsobj);
      var idargs = Module.hiwire_new_value(jsargs);
      var idresult = __pyproxy_apply(ptrobj, idargs);
      var jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idargs);
      return jsresult;
    },
  };

  return 0;
// clang-format on
});
