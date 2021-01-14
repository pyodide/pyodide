#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include "error_handling.h"
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

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
    result = PyObject_SetItem(pyobj, pykey, pyval);
  } else {
    result = PyObject_SetAttr(pyobj, pykey, pyval);
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
{ // See bug #1049
  Py_DECREF(ptrobj);
  EM_ASM({ delete Module.PyProxies[$0]; }, ptrobj);
}

EM_JS_REF(JsRef, pyproxy_new, (PyObject * ptrobj), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyproxy_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.
  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire.new_value(Module.PyProxies[ptrobj]);
  }

  _Py_IncRef(ptrobj);

  let target = function(){};
  target['$$'] = { ptr : ptrobj, type : 'PyProxy' };
  Object.assign(target, Module.PyProxyPublicMethods);
  let proxy = new Proxy(target, Module.PyProxyHandlers);
  Module.PyProxies[ptrobj] = proxy;

  return Module.hiwire.new_value(proxy);
});

EM_JS(int, pyproxy_init, (), {
  // clang-format off
  Module.PyProxies = {};
  function _getPtr(jsobj) {
    let ptr = jsobj['$$']['ptr'];
    if (ptr === null) {
      throw new Error("Object has already been destroyed");
    }
    return ptr;
  }
  // Static methods
  Module.PyProxy = {
    _getPtr,
    isPyProxy: function(jsobj) {
      return jsobj && jsobj['$$'] !== undefined && jsobj['$$']['type'] === 'PyProxy';
    },
  };

  Module.PyProxyPublicMethods = {
    toString : function() {
      let ptrobj = _getPtr(this);
      let jsref_repr = __pyproxy_repr(ptrobj);
      let repr = Module.hiwire.get_value(jsref_repr);
      Module.hiwire.decref(jsref_repr);
      return repr;
    },
    destroy : function() {
      let ptrobj = _getPtr(this);
      __pyproxy_destroy(ptrobj);
      this['$$']['ptr'] = null;
    },
    apply : function(jsthis, jsargs) {
      let idargs = Module.hiwire.new_value(jsargs);
      let idresult = __pyproxy_apply(ptrobj, idargs);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idargs);
      return jsresult;
    },
  };

  // See explanation of which methods should be defined here and what they do here:
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
  Module.PyProxyHandlers = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let result = __pyproxy_has(ptrobj, idkey) !== 0;
      Module.hiwire.decref(idkey);
      return result;
    },
    get: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey)){
        Reflect.get(jsobj, jskey);
      }
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyproxy_get(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    set: function (jsobj, jskey, jsval) {
      let ptrobj = _getPtr(jsobj);
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
      let ptrobj = _getPtr(jsobj);
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyproxy_deleteProperty(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return jsresult;
    },
    ownKeys: function (jsobj) {
      let result = Reflect.ownKeys(jsobj);
      let ptrobj = _getPtr(jsobj);
      let idresult = __pyproxy_ownKeys(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      result.push(...jsresult);
      return result;
    },
    apply: function (jsobj, jsthis, jsargs) {
      return jsobj.apply(jsthis, jsargs);
    },
  };

  return 0;
// clang-format on
});
