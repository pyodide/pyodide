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
  return hiwire_bool(hasattr);
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
  int idattr = python2js_nocopy(pyattr);
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
_pyobject_delattr(int ptrobj, int idkey)
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
    int identry = python2js_nocopy(pyentry);
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
  int idresult = python2js_nocopy(pyresult);
  Py_DECREF(pyresult);
  Py_DECREF(pyargs);
  return idresult;
}

void
_pyobject_decref(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_DECREF(ptrobj);
}

int
_pyobject_iter(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* iter = PyObject_GetIter(pyobj);
  if (iter == NULL) {
    return hiwire_undefined();
  }
  int iditer = python2js_nocopy(iter);
  Py_DECREF(iter);
  return iditer;
}

// PyIterator protocol
int
_pyiterator_next(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  int is_iter = PyIter_Check(pyobj);
  if (!is_iter) {
    return pythonexc2js();
  }
  PyObject* result = PyIter_Next(pyobj);
  if (result == NULL) {
    if (PyErr_Occurred()) {
      return pythonexc2js();
    }
    return hiwire_null();
  }
  int idresult = python2js_nocopy(result);
  Py_DECREF(result);
  return idresult;
}

// PyMappingProtocol Methods
/*
 * Return value is an ACTUAL integer not a hiwire index.
 */
int
_pymapping_length(int ptrobj)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  Py_ssize_t length = PyObject_Size(pyobj);
  if (length < 0) {
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
  PyErr_Clear();
  return hiwire_bool(item != NULL);
}

int
_pymapping_getitem(int ptrobj, int idkey)
{
  PyObject* pyobj = (PyObject*)ptrobj;
  PyObject* pykey = js2python(idkey);
  PyObject* item = PyObject_GetItem(pyobj, pykey);
  Py_DECREF(pykey);
  if (item == NULL) {
    // TODO: consider letting error propagate.
    // Would reduce inconsistency.
    PyErr_Clear();
    return hiwire_undefined();
  }

  int idattr = python2js_nocopy(item);
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

EM_JS(int, _pyproxy_use, (int ptrobj), { return Module.PyProxy._use(ptrobj); });

EM_JS(int, _pyproxy_new, (int ptrobj, int pytypeobjid), {
  let pytypeobj = Module.hiwire.get_value(pytypeobjid);
  let proxy = Module.PyProxy._new(ptrobj, pytypeobj);
  return Module.hiwire.new_value(proxy);
  // clang-format on
});

int
get_pyproxy(PyObject* obj)
{
  // Proxies we've already created are just returned again, so that the
  // same object on the Python side is always the same object on the
  // Javascript side.
  int result;
  result = _pyproxy_use((int)obj);
  if (result != HW_UNDEFINED) {
    return result;
  }

  int pytypeobjid = hiwire_object();

  int pytypeid = hiwire_string_ascii((int)obj->ob_type->tp_name);
  hiwire_set_member_string(pytypeobjid, (int)"py_type", pytypeid);
  hiwire_decref(pytypeid);

  int index_type_id = hiwire_int(PySequence_Check(obj) + PyMapping_Check(obj));
  hiwire_set_member_string(pytypeobjid, (int)"index_type", index_type_id);
  hiwire_decref(index_type_id);

  int can_copy = python2js_can_copy(obj);
  hiwire_set_member_string(pytypeobjid, (int)"can_copy", hiwire_bool(can_copy));

  int iter_type;
  if (PyIter_Check(obj)) {
    iter_type = 2;
  } else {
    PyObject* iter = PyObject_GetIter(obj);
    if (iter) {
      iter_type = 1;
      Py_CLEAR(iter);
    } else {
      iter_type = 0;
      PyErr_Clear();
    }
  }
  int iter_type_id = hiwire_int(iter_type);
  hiwire_set_member_string(pytypeobjid, (int)"iter_type", iter_type_id);
  hiwire_decref(iter_type_id);

  // Reference counter is increased only once when a PyProxy is created.
  Py_INCREF(obj);
  result = _pyproxy_new((int)obj, pytypeobjid);
  hiwire_decref(pytypeobjid);

  return result;
}

EM_JS(int, pyproxy_init, (), {
  // clang-format off
  // $$_null is actually a valid js identifier?!
  let $$_null = Object.freeze({ ptr : null, type : 'PyProxy' });
  let _PyProxy = {};
  _PyProxy.objects = new Map();

  Module.PyProxy = {
    isPyProxy : function(jsobj) {
      return jsobj["$$"] !== undefined && jsobj["$$"]['type'] === 'PyProxy';
    },
    _new : function(ptrobj, pytypeobj){
      // Technically, this leaks memory, since we're holding on to a reference
      // to the proxy forever.  But we have that problem anyway since we don't
      // have a destructor in Javascript to free the Python object.
      // PyProxy.destroy, which is a way for users to manually delete the proxy,
      // also deletes the proxy from this set.

      // In order to call the resulting proxy we need to make target be a function.
      let target = function(){ throw Error("This should never happen."); };
      Object.assign(target, _PyProxy.ObjectProtocol);
      let { py_type, index_type, iter_type, can_copy } = pytypeobj;
      if(index_type > 0){
        Object.assign(target, _PyProxy.MappingProtocol);
      }
      if(iter_type > 0){
        Object.assign(target, _PyProxy.IterableProtocol);
      }
      if(iter_type > 1){
        Object.assign(target, _PyProxy.IteratorProtocol);
      }
      if(can_copy){
        target["deep_to_js"] = _PyProxy.deep_to_js;
        target["shallow_to_js"] = _PyProxy.shallow_to_js;
      }
      target['$$'] = Object.freeze({ ptr : ptrobj, type : 'PyProxy', py_type, index_type, iter_type });

      for (let key in target) {
        if (typeof target[key] == 'function') {
          target[key] = target[key].bind(target);
        }
      }

      let proxy = new Proxy(target, _PyProxy.Handler);
      _PyProxy.objects.set(ptrobj, proxy);
      return proxy;
    },
    _use : function(ptrobj){
        // Checks if there is already an existing proxy on ptrobj
        if (_PyProxy.objects.has(ptrobj)) {
          return Module.hiwire.new_value(_PyProxy.objects.get(ptrobj));
        }
        return Module.hiwire.UNDEFINED;
    }
  };

  let pyprotos = {};

  pyprotos.object = {
    hasattr : function (jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyobject_hasattr(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    getattr : function (jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyobject_getattr(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    setattr : function(jsobj, jskey, jsval){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idval = Module.hiwire.new_value(jsval);
      let idresult = __pyobject_setattr(ptrobj, idkey, idval);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    delattr : function(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pyobject_delattr(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return jsresult;
    },
    dir : function(jsobj){
      let ptrobj = jsobj._getPtr();
      let idresult = __pyobject_dir(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return jsresult
    },
    call : function(jsobj, jsargs){
      let ptrobj = jsobj._getPtr();
      let idargs = Module.hiwire.new_value(jsargs);
      let idresult = __pyobject_call(ptrobj, idargs);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idargs);
      return jsresult;
    },
    iter : function(jsobj){
      let ptrobj = jsobj._getPtr();
      let idresult = __pyobject_iter(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    destroy : function(jsobj){
      let ptrobj = jsobj._getPtr();
      __pyobject_decref(ptrobj);
      _PyProxy.objects.delete(ptrobj);
    }
  };

  pyprotos.iterator = {
    next : function(jsobj) {
      let ptrobj = jsobj._getPtr();
      let idresult = __pyiterator_next(ptrobj);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return jsresult;
    }
  };

  pyprotos.mapping = {
    length : function(jsobj){
      return __pymapping_length(jsobj._getPtr());
    },
    hasitem : function(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pymapping_hasitem(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    getitem : function getitem(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pymapping_getitem(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    setitem : function setitem(jsobj, jskey, jsval){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idval = Module.hiwire.new_value(jsval);
      let idresult = __pymapping_setitem(ptrobj, idkey, idval);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
      Module.hiwire.decref(idresult);
      return jsresult;
    },
    delitem : function(jsobj, jskey){
      let ptrobj = jsobj._getPtr();
      let idkey = Module.hiwire.new_value(jskey);
      let idresult = __pymapping_delitem(ptrobj, idkey);
      let jsresult = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      Module.hiwire.decref(idkey);
      return jsresult;
    },
  };

  _PyProxy.ObjectProtocol = {
    _getPtr : function() {
      let ptr = this["$$"].ptr;
      if (ptr === null) {
        throw new Error("Object has already been destroyed");
      }
      return ptr;
    },
    toString : function() {
      if (self.pyodide.repr === undefined) {
        self.pyodide.repr = self.pyodide.pyimport('repr');
      }      
      return self.pyodide.repr(this);
    },
    destroy : function() {
      pyprotos.object.destroy(this);
      this["$$"] = $$_null;
    }
  };

  _PyProxy.deep_to_js = function(){
    let ptrobj = this._getPtr();
    let idval = _python2js_copy(ptrobj);
    let jsval = Module.hiwire.get_value(idval);
    Module.hiwire.decref(idval);
    return jsval;
  };

  _PyProxy.shallow_to_js = function(){
    throw Error("Not implemented...")
  };
  // Wrap PyMappingProtocol in the javascript Map api (as best as possible)
  // https://docs.python.org/3.8/c-api/mapping.html
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map
  _PyProxy.MappingProtocol = {
    has : function (jskey) {
      return pyprotos.mapping.hasitem(this, jskey);
    },
    get : function (jskey) {
      return pyprotos.mapping.getitem(this, jskey);
    },
    set : function (jskey, jsval) {
      return pyprotos.mapping.setitem(this, jskey, jsval);
    },
    delete : function (jskey, jsval) {
      return pyprotos.mapping.delitem(this, jskey);
    },
    // Cannot call this length, causes 
    // "TypeError: Cannot assign to read only property 'length' of function ..."
    len : function(){ 
      return pyprotos.mapping.length(this);
    }
  };

  _PyProxy.IterableProtocol = {
    [Symbol.iterator] : function(){
      return pyprotos.object.iter(this);
    }
  };

  _PyProxy.IteratorProtocol = {
    next : function(){
      let result = pyprotos.iterator.next(this);
      if(result === null){
        return {done : true};
      }
      return {value : result, done : false};
    }
  };

  function isStrInteger(str){
    return !Number.isNaN(str) && Number.isInteger(Number.parseFloat(str));
  }
  
  function shouldIndexSequence (jsobj, jskey){
    return jsobj["$$"].index_type === 2 && isStrInteger(jskey);
  };

  // Proxy trap names (stared means we implement it):
  // getPrototypeOf, setPrototypeOf, *isExtensible, preventExtensions, *getOwnPropertyDescriptor
  // defineProperty, *deleteProperty,  *has, *get, *set, *ownKeys, *apply, construct

  // We must include "non-configurable own properties of the target object" in the results of
  // has, get, set, and getOwnPropertyDescriptor. The target object is a function (so we can call it).
  // Its "nonconfigurable own properties" are "arguments", "caller", and "prototype".
  _PyProxy.Handler = {
    isExtensible: function() { return true },
    has : function (jsobj, jskey) {
      if(jskey === "length" || jskey === "size"){
        return Reflect.has(jsobj, "len");
      }
      if(Reflect.has(jsobj, jskey)){
        return true;
      }
      if(shouldIndexSequence(jsobj, jskey)){
        return pyprotos.mapping.hasitem(jsobj, Number.parseInt(jskey));
      }
      return pyprotos.object.hasattr(jsobj, jskey);
    },
    get : function (jsobj, jskey) {
      if(jskey === "length" || jskey === "size"){
        let len_func = Reflect.get(jsobj, "len");
        return len_func && len_func();
      }
      if(Reflect.has(jsobj, jskey)){
        return Reflect.get(jsobj, jskey);
      }
      if(shouldIndexSequence(jsobj, jskey)){
        return pyprotos.mapping.getitem(jsobj, Number.parseInt(jskey));
      }
      return pyprotos.object.getattr(jsobj, jskey);
    },
    set : function (jsobj, jskey, jsval) {
      if(jskey === "length" || jskey === "size"){
        throw new Error(`Cannot change builtin field "${jskey}"`);
      }      
      if(Reflect.has(jsobj, jskey)){
        throw new Error(`Cannot change builtin field "${jskey}"`);
      }
      if(shouldIndexSequence(jsobj, jskey)){
        return pyprotos.mapping.setitem(jsobj, Number.parseInt(jskey), jsval);
      }
      return pyprotos.object.setattr(jsobj, jskey, jsval);
    },
    deleteProperty : function (jsobj, jskey) {
      if(Reflect.has(jsobj, jskey)){
        throw new Error(`Cannot change builtin field "${jskey}"`);
      }      
      if(shouldIndexSequence(jsobj, jskey)){
        return pyprotos.mapping.delitem(jsobj, Number.parseInt(jskey));
      }      
      return pyprotos.object.delattr(jsobj, jskey);
    },
    ownKeys : function (jsobj) {
      let jsresult = pyprotos.object.dir(jsobj);
      jsresult.push(...Reflect.ownKeys(jsobj));
      return jsresult;
    },
    apply : function (jsobj, jsthis, jsargs) {
      return pyprotos.object.call(jsobj, jsargs);
    },
    getOwnPropertyDescriptor : function(target, prop){
      if(prop in target){
        let result = Object.getOwnPropertyDescriptor(target, prop);
        let hidden = prop === "$$" || prop === "_getPtr";
        result.enumerable &= !hidden;
        if(prop === "length" && Reflect.has(target, "len")){
          result.enumerable = true;
        }
        return result;
      }
      if(!(this.has(target, prop))){
        return undefined;
      }
      let value = this.get(target, prop);
      // "enumerable" controls which properties appear when we loop using 
      // for(let x in py_object), and also which properties appear in Object.keys(py_object)
      let enumerable = true; // !prop.startsWith("_")??
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