#include <Python.h>
#include <emscripten.h>

#include "hiwire.h"
#include "js2python.h"
#include "python2js.h"

// PyObjectProtocol Methods
int
_pyobject_hasattr(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  int hasattr = PyObject_HasAttr(pyobj, pykey);
  Py_DECREF(pykey);
  return hasattr ? hiwire_true() : hiwire_false();
}

int
_pyobject_getattr(int ptrobj, int idkey)
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
_pyobject_setattr(int ptrobj, int idkey, int idval)
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
_pyobject_dir(int ptrobj)
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
_pyobject_call(int ptrobj, int idargs)
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
_pyobject_destroy(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_DECREF(ptrobj);
  EM_ASM(delete Module.PyProxies[ptrobj];);
}

int
_pyobject_iter(int ptrobj){
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* iter = PyObject_GetIter(pyobj);
  if(iter == NULL){
    return hiwire_undefined();
  }
  int iditer = python2js(iter);
  Py_DECREF(iter);
  return iditer;
}

// PyIterator protocol
int
_pyiterator_next(int ptrobj){
  PyObject* pyobj = (PyObject*)ptrobj;
  int is_iter = PyIter_Check(pyobj);
  if(!is_iter){
    return pythonexc2js();
  }
  PyObject *result = PyIter_Next(pyobj);
  if(result == NULL){
    if(PyErr_Occurred()){
      return pythonexc2js();
    }
    return hiwire_null();
  }
  int idresult = python2js(result);
  Py_DECREF(result);
  return idresult;
}

// PyMappingProtocol Methods
int
_pymapping_length(int ptrobj){
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_ssize_t length = PyObject_Size(pyobj);
  if(length < 0){
    return pythonexc2js();
  }
  return length;
}


int
_pymapping_hasitem(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* item = PyObject_GetItem(pyobj, pykey);
  Py_DECREF(pykey);
  if (item == NULL) {
    PyErr_Clear();
    return hiwire_false();
  } else {
    return hiwire_true();
  }
}

int
_pymapping_getitem(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* item = PyObject_GetItem(pyobj, pykey);
  Py_DECREF(pykey);
  if (item == NULL) {
    PyErr_Clear();
    return hiwire_undefined();
  }

  int idattr = python2js(item);
  Py_DECREF(item);
  return idattr;
};

int
_pymapping_setitem(int ptrobj, int idkey, int idval)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* pyval = js2python(idval);
  int result = PyObject_SetItem(pyobj, pykey, pyval);
  Py_DECREF(pykey);
  Py_DECREF(pyval);

  if (result) {
    return pythonexc2js();
  }
  return idval;
}

int
_pymapping_delitem(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);

  int ret = PyObject_DelItem(pyobj, pykey);
  Py_DECREF(pykey);

  if (ret) {
    return pythonexc2js();
  }

  return hiwire_undefined();
}




EM_JS(int, _pyproxy_use, (int ptrobj), {
  // Checks if there is already an existing proxy on ptrobj

  if (Module.PyProxies.hasOwnProperty(ptrobj)) {
    return Module.hiwire_new_value(Module.PyProxies[ptrobj]);
  }

  return -2; /* this means HW_UNDEFINED */
})

EM_JS(int, _pyproxy_new, (int ptrobj, int pytypeid, int index_type, int iter_type), {
  // Technically, this leaks memory, since we're holding on to a reference
  // to the proxy forever.  But we have that problem anyway since we don't
  // have a destructor in Javascript to free the Python object.
  // _pyobject_destroy, which is a way for users to manually delete the proxy,
  // also deletes the proxy from this set.
  // clang-format off
  
  // In order to call the resulting proxy we need to make target be a function.
  // Any function will do, it will never be called.
  let pytype = Module.hiwire_get_value(pytypeid);
  let target = function(){throw Error("This should never happen.")};
  Object.assign(target, Module.PyProxyTarget);
  if(index_type > 0){
    Object.assign(target, Module.PyProxy.MappingProtocol);
  }
  if(iter_type > 0){
    Object.assign(target, Module.PyProxy.IterableProtocol);
  }
  if(iter_type > 1){
    Object.assign(target, Module.PyProxy.IteratorProtocol);
  }
  target['$$'] = Object.freeze({ ptr : ptrobj, type : 'PyProxy', pytype, index_type, iter_type });

  let proxy = new Proxy(target, Module.PyProxyHandler);
  Module.PyProxies[ptrobj] = proxy;
  return Module.hiwire_new_value(proxy);
  // clang-format on
});

int get_pyproxy(PyObject *obj){
  // Proxies we've already created are just returned again, so that the
  // same object on the Python side is always the same object on the
  // Javascript side.
  int result;
  result = _pyproxy_use((int)obj);
  if (result != HW_UNDEFINED) {
    return result;
  }

  int pytypeid = hiwire_string_ascii((int)obj->ob_type->tp_name);
  int index_type = PySequence_Check(obj) + PyMapping_Check(obj);
  int iter_type = 0;
  if(PyIter_Check(obj)){
    iter_type = 2;
  } else {
    PyObject* iter = PyObject_GetIter(obj);
    if(iter){
      iter_type = 1;
      Py_CLEAR(iter);
    }
  }
  
  Py_INCREF(obj);
  result = _pyproxy_new((int)obj, pytypeid, index_type, iter_type);
  hiwire_decref(pytypeid);

  // Reference counter is increased only once when a PyProxy is created.
  return result;
}

EM_JS(int, pyproxy_init, (), {
  // clang-format off
  Module.PyProxies = {};
  Module.helpers = {
    isStrInteger : function isStrInteger(str){
      return !Number.isNaN(str) && Number.isInteger(Number.parseFloat(str));
    },
    shouldIndexSequence : function(jsobj, jskey){
      return jsobj["$$"].index_type === 2 && Module.helpers.isStrInteger(jskey);
    }
  };

  Module.pyprotowrappers = {};

  Module.pyprotowrappers.object = {
    hasattr : function hasattr(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pyobject_hasattr(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    getattr : function hasattr(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pyobject_getattr(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    setattr : function(jsobj, jskey, jsval){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idval = Module.hiwire_new_value(jsval);
      let idresult = __pyobject_setattr(ptrobj, idkey, idval);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idval);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    delattr : function(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pyobject_delattr(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idkey);
      return jsresult;
    },
    dir : function(jsobj){
      let ptrobj = jsobj._getPtr();
      let idresult = __pyobject_dir(ptrobj);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      return jsresult
    },
    call : function(jsobj, jsargs){
      let ptrobj = jsobj._getPtr();
      let idargs = Module.hiwire_new_value(jsargs);
      let idresult = __pyobject_call(ptrobj, idargs);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idargs);
      return jsresult;
    },
    iter : function(jsobj){
      let ptrobj = jsobj._getPtr();
      let idresult = __pyobject_iter(ptrobj);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      return jsresult;
    }
  };

  Module.pyprotowrappers.iterator = {
    next : function(jsobj) {
      let ptrobj = jsobj._getPtr();
      let idresult = __pyiterator_next(ptrobj);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      return jsresult;
    }
  };

  Module.pyprotowrappers.mapping = {
    length : function length(jsobj){
      let ptrobj = jsobj._getPtr();
      let idresult = __pymapping_length(ptrobj);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    hasitem : function hasattr(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pymapping_hasitem(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    getitem : function getitem(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pymapping_getitem(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    setitem : function setitem(jsobj, jskey, jsval){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idval = Module.hiwire_new_value(jsval);
      let idresult = __pymapping_setitem(ptrobj, idkey, idval);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idkey);
      Module.hiwire_decref(idval);
      Module.hiwire_decref(idresult);
      return jsresult;
    },
    delitem : function(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire_new_value(jskey);
      let idresult = __pymapping_delitem(ptrobj, idkey);
      let jsresult = Module.hiwire_get_value(idresult);
      Module.hiwire_decref(idresult);
      Module.hiwire_decref(idkey);
      return jsresult;
    },
  };

  Module["$$-null"] = Object.freeze({ ptr : null, type : 'PyProxy' });
  Module.PyProxy = {
    isPyProxy : function isPyProxy(jsobj) {
      return jsobj["$$"] !== undefined && jsobj["$$"]['type'] === 'PyProxy';
    }
  };

  Module.PyProxyTarget = {
    _getPtr : function _getPtr() {
      let ptr = this["$$"].ptr;
      if (ptr === null) {
        throw new Error("Object has already been destroyed");
      }
      return ptr;
    },
    toString : function toString() {
      if (self.pyodide.repr === undefined) {
        self.pyodide.repr = self.pyodide.pyimport('repr');
      }      
      return self.pyodide.repr(this);
    },
    destroy : function destroy() {
      __pyobject_destroy(ptrobj);
      this["$$"].ptr = Module["$$-null"];
    }
  };

  // Wrap PyMappingProtocol in the javascript Map api (as best as possible)
  // https://docs.python.org/3.8/c-api/mapping.html
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map
  Module.PyProxy.MappingProtocol = {
    has: function (jskey) {
      return Module.pyprotowrappers.mapping.hasitem(this, Number.parseInt(jskey));
    },
    get: function (jskey) {
      return Module.pyprotowrappers.mapping.getitem(this, Number.parseInt(jskey));
    },
    set: function (jskey, jsval) {
      return Module.pyprotowrappers.mapping.setitem(this, Number.parseInt(jskey));
    },
    delete: function (jskey, jsval) {
      return Module.pyprotowrappers.mapping.delitem(this, Number.parseInt(jskey));
    },
  };

  Module.PyProxy.IterableProtocol = {
    [Symbol.iterator] : function(){
      return Module.pyprotowrappers.object.iter(this);
    }
  };

  Module.PyProxy.IteratorProtocol = {
    next : function(){
      let result = Module.pyprotowrappers.iterator.next(this);
      if(result === null){
        return {done : true};
      }
      return {value : result, done : false};
    }
  };

// getPrototypeOf, setPrototypeOf, *isExtensible, preventExtensions, *getOwnPropertyDescriptor
// defineProperty, *deleteProperty,  *has, *get, *set, *ownKeys, *apply, construct
  Module.PyProxyHandler = {
    isExtensible: function() { return true },
    has: function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey)){
        return true;
      }
      if(Module.helpers.shouldIndexSequence(jsobj, jskey)){
        return Module.helpers.hasitem(jsobj, Number.parseInt(jskey));
      }
      return Module.helpers.hasattr(jsobj, jskey);
    },
    get: function (jsobj, jskey) {
      ptrobj = jsobj._getPtr();
      if(Reflect.has(jsobj, jskey)){
        return Reflect.get(jsobj, jskey);
      }
      if(Module.helpers.shouldIndexSequence(jsobj, jskey)){
        return Module.helpers.getitem(jsobj, Number.parseInt(jskey));
      }
      return Module.helpers.getattr(jsobj, jskey);
    },
    set: function (jsobj, jskey, jsval) {
      console.log("proxy set");
      if(Reflect.has(jsobj, jskey)){
        throw Error(`Cannot change built-in field {jskey}`);
        return Reflect.set(jsobj, jskey, jsval);
      }
      if(Module.helpers.shouldIndexSequence(jsobj, jskey)){
        return Module.helpers.setitem(jsobj, Number.parseInt(jskey));
      }
      return Module.helpers.setattr(jsobj, jskey, jsval);
    },
    deleteProperty: function (jsobj, jskey) {
      if(Module.helpers.shouldIndexSequence(jsobj, jskey)){
        return Module.helpers.delitem(jsobj, Number.parseInt(jskey));
      }      
      return Module.helpers.delattr(jsobj, jskey);
    },
    ownKeys: function (jsobj) {
      let jsresult = Module.helpers.dir(jsobj);
      jsresult.push('toString', 'prototype', 'arguments', 'caller');
      return jsresult;
    },
    apply: function (jsobj, jsthis, jsargs) {
      return Module.helpers.call(jsobj, jsargs);
    },
    getOwnPropertyDescriptor : function(target, prop){
      if(prop in target){
        return Object.getOwnPropertyDescriptor(target, prop);
      }
      if(!(this.has(target, prop))){
        return undefined;
      }
      let value = this.get(target, prop);
      // "enumerable" controls which properties appear when we loop using 
      // for(let x in py_object), and also which properties appear in Object.keys(py_object)
      let enumerable = !prop.startsWith("_");
      let writable = true;
      let configurable = true;
      let result = {value, writable, enumerable, configurable};
      return result;
    },
    construct : function() {/* TODO */},
  };

  return 0;
// clang-format on
});