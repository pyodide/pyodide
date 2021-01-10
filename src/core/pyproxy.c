#include "error_handling.h"
#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

_Py_IDENTIFIER(__builtins__);

JsRef
_pyproxy_repr(PyObject* pyobj)
{
  PyObject* repr_py = PyObject_Repr(pyobj);
  const char* repr_utf8 = PyUnicode_AsUTF8(repr_py);
  JsRef repr_js = hiwire_string_utf8(repr_utf8);
  Py_CLEAR(repr_py);
  return repr_js;
}

JsRef
_pyproxy_has(PyObject* pyobj, JsRef idkey)
{
  bool success = false;
  bool found_item;
  PyObject* pykey = NULL;
  PyObject* builtins;
  PyObject* item;
  JsRef result = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  if (!PyDict_Check(pyobj)) {
    item = PyObject_GetAttr(pyobj, pykey);
    FAIL_IF_ERR_NOT_MATCHES(PyExc_AttributeError);
  } else {
    item = PyDict_GetItemWithError(pyobj, pykey);
    Py_XINCREF(item);
    FAIL_IF_ERR_OCCURRED();
  }
  PyErr_Clear();

  if (item == NULL && PyDict_Check(pyobj)) {
    // Not found. Maybe this is a namespace? Try a builtin.
    builtins = _PyDict_GetItemIdWithError(pyobj, &PyId___builtins__);
    Py_XINCREF(builtins);
    FAIL_IF_ERR_OCCURRED();
    if (builtins != NULL) {
      item = PyDict_GetItemWithError(builtins, pykey);
      Py_XINCREF(item);
      FAIL_IF_ERR_OCCURRED();
    }
  }
  PyErr_Clear();

  result = hiwire_bool(item != NULL);
  success = true;
finally:
  Py_CLEAR(item);
  Py_CLEAR(pykey);
  Py_CLEAR(builtins);
  if (!success) {
    hiwire_CLEAR(result);
  }
  return result;
}

/**
 * If _pyproxy_get succeeds but the key is not found, it returns
 * hiwire_undefined. (Is this what we should do?) If the object is a dict with a
 * __builtins__ field, treat it as a global namespace. In this case if the key
 * is not found as an item in the dict, try looking it up in __builtins__. This
 * mimics normal python name resolution on a global namespace.
 */
JsRef
_pyproxy_get(PyObject* pyobj, JsRef idkey)
{
  bool success = false;
  PyObject* pykey = NULL;
  PyObject* pyresult = NULL;
  PyObject* builtins = NULL;
  // result:
  JsRef result = NULL;

  pykey = js2python(idkey);
  FAIL_IF_NULL(pykey);
  // HC: HACK until my more thorough rework of pyproxy goes through.
  // We need globals to work, I want it to be proxied, but we also need
  // indexing in js to do GetItem, SetItem, and DelItem.
  // This is harmless though because currently dicts will not get proxied at
  // all, aside from globals which I specifically hand proxy in runpython.c.
  if (PyDict_Check(pyobj)) {
    pyresult = PyDict_GetItemWithError(pyobj, pykey);
    Py_XINCREF(pyresult);
    FAIL_IF_ERR_OCCURRED();
  } else {
    pyresult = PyObject_GetAttr(pyobj, pykey);
    FAIL_IF_ERR_NOT_MATCHES(PyExc_AttributeError);
  }

  PyErr_Clear();

  if (pyresult == NULL && PyDict_Check(pyobj)) {
    // Not found. Maybe this is a namespace? Try a builtin.
    builtins = _PyDict_GetItemIdWithError(pyobj, &PyId___builtins__);
    Py_XINCREF(builtins);
    FAIL_IF_ERR_OCCURRED();
    if (builtins != NULL) {
      pyresult = PyDict_GetItemWithError(builtins, pykey);
      Py_XINCREF(pyresult);
      FAIL_IF_ERR_OCCURRED();
    }
  }

  PyErr_Clear();
  if (pyresult == NULL) {
    result = hiwire_undefined();
  } else {
    result = python2js(pyresult);
  }
  FAIL_IF_NULL(result);

  success = true;
finally:
  Py_CLEAR(pykey);
  Py_CLEAR(pyresult);
  Py_CLEAR(builtins);
  if (!success) {
    hiwire_CLEAR(result);
  }
  return result;
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
    return NULL;
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
    return NULL;
  }

  return hiwire_undefined();
}

JsRef
_pyproxy_ownKeys(PyObject* pyobj)
{
  PyObject* pydir = PyObject_Dir(pyobj);

  if (pydir == NULL) {
    pythonexc2js();
    return NULL;
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
    return NULL;
  }
  JsRef idresult = python2js(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
  return idresult;
}

void
_pyproxy_destroy(PyObject* ptrobj)
{
  Py_DECREF(ptrobj);
  EM_ASM({ delete Module.PyProxies[$0]; }, ptrobj);
}

EM_JS_REF(JsRef, pyproxy_use, (PyObject * ptrobj), {
  // Checks if there is already an existing proxy on ptrobj

  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire.new_value(Module.PyProxies[ptrobj]);
  }

  return Module.hiwire.ERROR;
})

EM_JS_REF(JsRef, pyproxy_new, (PyObject * ptrobj), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.

  let target = function(){};
  target['$$'] = { ptr : ptrobj, type : 'PyProxy' };
  let proxy = new Proxy(target, Module.PyProxy);
  Module.PyProxies[ptrobj] = proxy;

  return Module.hiwire.new_value(proxy);
});

EM_JS_NUM(int, pyproxy_init, (), {
  // clang-format off
  Module.PyProxies = {};
  Module.PyProxy = {
    getPtr: function(jsobj) {
      let ptr = jsobj['$$']['ptr'];
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
      let ptrobj = this.getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyproxy_has(ptrobj, idkey);
      let result = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return result;
    },
    get: function (jsobj, jskey) {
      let ptrobj = this.getPtr(jsobj);
      if (jskey === 'toString') {
        return function() {
          let jsref_repr = __pyproxy_repr(ptrobj);
          let repr = Module.hiwire.get_value(jsref_repr);
          Module.hiwire.decref(jsref_repr);
          return repr;
        }
      } else if (jskey === '$$') {
        return jsobj['$$'];
      } else if (jskey === 'destroy') {
        return function() {
          __pyproxy_destroy(ptrobj);
          jsobj['$$']['ptr'] = null;
        }
      } else if (jskey === 'apply') {
        return function(jsthis, jsargs) {
          let idargs = Module.hiwire.new_value(jsargs);
          let idresult = __pyproxy_apply(ptrobj, idargs);
          let jsresult = Module.hiwire.get_value(idresult);
          Module.hiwire.decref(idresult);
          Module.hiwire.decref(idargs);
          return jsresult;
        };
      }
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyproxy_get(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    set: function (jsobj, jskey, jsval) {
      let ptrobj = this.getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idval = Module.hiwire.new_value(jsval);
      let idresult = __pyproxy_set(ptrobj, idkey, idval);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    deleteProperty: function (jsobj, jskey) {
      let ptrobj = this.getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyproxy_deleteProperty(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return jsresult;
    },
    ownKeys: function (jsobj) {
      let ptrobj = this.getPtr(jsobj);
      let idresult = __pyproxy_ownKeys(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    enumerate: function (jsobj) {
      let ptrobj = this.getPtr(jsobj);
      let idresult = __pyproxy_enumerate(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      this.addExtraKeys(jsresult);
      return jsresult;
    },
    apply: function (jsobj, jsthis, jsargs) {
      let ptrobj = this.getPtr(jsobj);
      let idargs = Module.hiwire.new_value(jsargs);
      let idresult = __pyproxy_apply(ptrobj, idargs);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idargs);
      return jsresult;
    },
  };

  return 0;
// clang-format on
});
