#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

JsRef
_pyproxy_has(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  JsRef result = hiwire_bool(PyObject_HasAttr(pyobj, pykey));
  Py_DECREF(pykey);
  return result;
}

JsRef
_pyproxy_get(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  PyObject* pyattr;
  // HC: HACK until my more thorough rework of pyproxy goes through.
  // We need globals to work, I want it to be proxied, but we also need
  // indexing in js to do GetItem, SetItem, and DelItem.
  // This is harmless though because currently dicts will not get proxied at
  // all, aside from globals which I specifically hand proxy in runpython.c.
  if (PyDict_Check(pyobj)) {
    pyattr = PyObject_GetItem(pyobj, pykey);
  } else {
    pyattr = PyObject_GetAttr(pyobj, pykey);
  }

  Py_DECREF(pykey);
  if (pyattr == NULL) {
    PyErr_Clear();
    return hiwire_undefined();
  }

  JsRef idattr = python2js(pyattr);
  Py_DECREF(pyattr);
  return idattr;
};

JsRef
_pyproxy_set(PyObject* pyobj, JsRef idkey, JsRef idval)
{
  PyObject* pykey = js2python(idkey);
  PyObject* pyval = js2python(idval);
  // HC: HACK see comment in _pyproxy_get.
  int result;
  if (PyDict_Check(pyobj)) {
    PyObject_SetItem(pyobj, pykey, pyval);
  } else {
    PyObject_SetAttr(pyobj, pykey, pyval);
  }
  Py_DECREF(pykey);
  Py_DECREF(pyval);

  if (result) {
    pythonexc2js();
    return Js_ERROR;
  }
  return idval;
}

JsRef
_pyproxy_deleteProperty(PyObject* pyobj, JsRef idkey)
{
  PyObject* pykey = js2python(idkey);
  int ret;
  // HC: HACK see comment in _pyproxy_get.
  if (PyDict_Check(pyobj)) {
    ret = PyObject_DelItem(pyobj, pykey);
  } else {
    ret = PyObject_DelAttr(pyobj, pykey);
  }
  Py_DECREF(pykey);

  if (ret) {
    pythonexc2js();
    return Js_ERROR;
  }

  return hiwire_undefined();
}

JsRef
_pyproxy_ownKeys(PyObject* pyobj)
{
  PyObject* pydir = PyObject_Dir(pyobj);

  if (pydir == NULL) {
    pythonexc2js();
    return Js_ERROR;
  }

  JsRef iddir = hiwire_array();
  Py_ssize_t n = PyList_Size(pydir);
  for (Py_ssize_t i = 0; i < n; ++i) {
    PyObject* pyentry = PyList_GetItem(pydir, i);
    JsRef identry = python2js(pyentry);
    hiwire_push_array(iddir, identry);
    hiwire_decref(identry);
  }
  Py_DECREF(pydir);

  return iddir;
}

JsRef
_pyproxy_enumerate(PyObject* pyobj)
{
  return _pyproxy_ownKeys(pyobj);
}

JsRef
_pyproxy_apply(PyObject* pyobj, JsRef idargs)
{
  Py_ssize_t length = hiwire_get_length(idargs);
  PyObject* pyargs = PyTuple_New(length);
  for (Py_ssize_t i = 0; i < length; ++i) {
    JsRef iditem = hiwire_get_member_int(idargs, i);
    PyObject* pyitem = js2python(iditem);
    PyTuple_SET_ITEM(pyargs, i, pyitem);
    hiwire_decref(iditem);
  }
  PyObject* pyresult = PyObject_Call(pyobj, pyargs, NULL);
  if (pyresult == NULL) {
    Py_DECREF(pyargs);
    pythonexc2js();
    return Js_ERROR;
  }
  JsRef idresult = python2js(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
  return idresult;
}

void
_pyproxy_destroy(PyObject* ptrobj)
{
  PyObject* pyobj = ptrobj;
  Py_DECREF(ptrobj);
  EM_ASM(delete Module.PyProxies[ptrobj];);
}

EM_JS(JsRef, pyproxy_use, (PyObject * ptrobj), {
  // Checks if there is already an existing proxy on ptrobj

  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire.new_value(Module.PyProxies[ptrobj]);
  }

  return Module.hiwire.ERROR;
})

EM_JS(JsRef, pyproxy_new, (PyObject * ptrobj), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.

  var target = function(){};
  target['$$'] = { ptr : ptrobj, type : 'PyProxy' };
  var proxy = new Proxy(target, Module.PyProxy);
  Module.PyProxies[ptrobj] = proxy;

  return Module.hiwire.new_value(proxy);
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
      var idkey = Module.hiwire.new_value(jskey);
      var result = __pyproxy_has(ptrobj, idkey) != 0;
      Module.hiwire.decref(idkey);
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
          var idargs = Module.hiwire.new_value(jsargs);
          var idresult = __pyproxy_apply(ptrobj, idargs);
          var jsresult = Module.hiwire.get_value(idresult);
          Module.hiwire.decref(idresult);
          Module.hiwire.decref(idargs);
          return jsresult;
        };
      }
      var idkey = Module.hiwire.new_value(jskey);
      var idresult = __pyproxy_get(ptrobj, idkey);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    set: function (jsobj, jskey, jsval) {
      ptrobj = this.getPtr(jsobj);
      var idkey = Module.hiwire.new_value(jskey);
      var idval = Module.hiwire.new_value(jsval);
      var idresult = __pyproxy_set(ptrobj, idkey, idval);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    deleteProperty: function (jsobj, jskey) {
      ptrobj = this.getPtr(jsobj);
      var idkey = Module.hiwire.new_value(jskey);
      var idresult = __pyproxy_deleteProperty(ptrobj, idkey);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return jsresult;
    },
    ownKeys: function (jsobj) {
      ptrobj = this.getPtr(jsobj);
      var idresult = __pyproxy_ownKeys(ptrobj);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    enumerate: function (jsobj) {
      ptrobj = this.getPtr(jsobj);
      var idresult = __pyproxy_enumerate(ptrobj);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    apply: function (jsobj, jsthis, jsargs) {
      ptrobj = this.getPtr(jsobj);
      var idargs = Module.hiwire.new_value(jsargs);
      var idresult = __pyproxy_apply(ptrobj, idargs);
      var jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idargs);
      return jsresult;
    },
  };

  return 0;
// clang-format on
});
