// This file to be included from pyproxy.c
//
// The point is to make a file that works with JsDoc. JsDoc will give up if it
// fails to parse the file as javascript. Thus, it's key that this file should
// parse as valid javascript. `TEMP_EMJS_HELPER` is a specially designed macro
// to allow us to do this. We need TEMP_EMJS_HELPER to parse like a javascript
// function call. The easiest way to get it to parse is to make the "argument"
// look like a function call, which we do with `()=>{`. However, `()=>{` is an
// invalid C string so the macro needs to remove it. We put `()=>{0,`,
// TEMP_EMJS_HELPER removes everything up to the comma and replace it with a
// single open brace.
//
// See definition of TEMP_EMJS_HELPER:
// #define TEMP_EMJS_HELPER(a, args...) \
//   EM_JS(int, pyproxy_init, (), UNPAIRED_OPEN_BRACE { args return 0; })

// clang-format off
TEMP_EMJS_HELPER(() => {0,0; /* Magic, see comment */
  // clang-format on

  if (globalThis.FinalizationRegistry) {
    Module.finalizationRegistry =
        new FinalizationRegistry((ptr) => { _Py_DecRef(ptr); });
  } else {
    Module.finalizationRegistry = {register() {}, unregister() {}};
  }

  function _getPtr(jsobj) {
    let ptr = jsobj.$$.ptr;
    if (ptr === null) {
      throw new Error("Object has already been destroyed");
    }
    return ptr;
  }

  let _pyproxyClassMap = new Map();
  /**
   * Retreive the appropriate mixins based on the features requested in flags.
   * Used by pyproxy_new. The "flags" variable is produced by the C function
   * pyproxy_getflags. Multiple PyProxies with the same set of feature flags
   * will share the same prototype, so the memory footprint of each individual
   * PyProxy is minimal.
   */
  Module.getPyProxyClass = function(flags) {
    let result = _pyproxyClassMap.get(flags);
    if (result) {
      return result;
    }
    let descriptors = {};
    // clang-format off
    for(let [feature_flag, methods] of [
      [HAS_LENGTH, Module.PyProxyLengthMethods],
      [HAS_GET, Module.PyProxyGetItemMethods],
      [HAS_SET, Module.PyProxySetItemMethods],
      [HAS_CONTAINS, Module.PyProxyContainsMethods],
      [IS_ITERABLE, Module.PyProxyIterableMethods],
      [IS_ITERATOR, Module.PyProxyIteratorMethods],
      [IS_AWAITABLE, Module.PyProxyAwaitableMethods],
      [IS_BUFFER, Module.PyProxyBufferMethods],
      [IS_CALLABLE, Module.PyProxyCallableMethods],
    ]){
      // clang-format on
      if (flags & feature_flag) {
        Object.assign(descriptors, Object.getOwnPropertyDescriptors(methods));
      }
    }
    let new_proto = Object.create(Module.PyProxyClass.prototype, descriptors);
    function PyProxy() {};
    PyProxy.prototype = new_proto;
    _pyproxyClassMap.set(flags, PyProxy);
    return PyProxy;
  };

  // Static methods
  Module.PyProxy = {
    _getPtr,
    isPyProxy : function(jsobj) {
      return jsobj && jsobj.$$ !== undefined && jsobj.$$.type === 'PyProxy';
    },
  };

  Module.callPyObject = function(ptrobj, ...jsargs) {
    let idargs = Module.hiwire.new_value(jsargs);
    let idresult;
    try {
      idresult = __pyproxy_apply(ptrobj, idargs);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idargs);
    }
    if (idresult === 0) {
      _pythonexc2js();
    }
    return Module.hiwire.pop_value(idresult);
  };

  // Now a lot of boilerplate to wrap the abstract Object protocol wrappers
  // above in Javascript functions.

  Module.PyProxyClass = class {
    constructor() { throw new TypeError('PyProxy is not a constructor'); }

    get[Symbol.toStringTag]() { return "PyProxy"; }
    get type() {
      let ptrobj = _getPtr(this);
      return Module.hiwire.pop_value(__pyproxy_type(ptrobj));
    }
    toString() {
      let ptrobj = _getPtr(this);
      let jsref_repr;
      try {
        jsref_repr = __pyproxy_repr(ptrobj);
      } catch (e) {
        Module.fatal_error(e);
      }
      if (jsref_repr === 0) {
        _pythonexc2js();
      }
      return Module.hiwire.pop_value(jsref_repr);
    }
    destroy() {
      let ptrobj = _getPtr(this);
      Module.finalizationRegistry.unregister(this);
      _Py_DecRef(ptrobj);
      this.$$.ptr = null;
    }
    /**
     * This one doesn't follow the pattern: the inner function
     * _python2js_with_depth is defined in python2js.c and is not a Python
     * Object Protocol wrapper.
     */
    toJs(depth = -1) {
      let idresult = _python2js_with_depth(_getPtr(this), depth);
      let result = Module.hiwire.get_value(idresult);
      Module.hiwire.decref(idresult);
      return result;
    }
    apply(jsthis, jsargs) {
      return Module.callPyObject(_getPtr(this), ...jsargs);
    }
    call(jsthis, ...jsargs) {
      return Module.callPyObject(_getPtr(this), ...jsargs);
    }
  };

  // Controlled by HAS_LENGTH, appears for any object with __len__ or sq_length
  // or mp_length methods
  Module.PyProxyLengthMethods = {
    get length() {
      let ptrobj = _getPtr(this);
      let length;
      try {
        length = _PyObject_Size(ptrobj);
      } catch (e) {
        Module.fatal_error(e);
      }
      if (length === -1) {
        _pythonexc2js();
      }
      return length;
    }
  };

  // Controlled by HAS_GET, appears for any class with __getitem__,
  // mp_subscript, or sq_item methods
  Module.PyProxyGetItemMethods = {
    get : function(key) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let idresult;
      try {
        idresult = __pyproxy_getitem(ptrobj, idkey);
      } catch (e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if (idresult === 0) {
        if (Module._PyErr_Occurred()) {
          _pythonexc2js();
        } else {
          return undefined;
        }
      }
      return Module.hiwire.pop_value(idresult);
    },
  };

  // Controlled by HAS_SET, appears for any class with __setitem__, __delitem__,
  // mp_ass_subscript,  or sq_ass_item.
  Module.PyProxySetItemMethods = {
    set : function(key, value) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let idval = Module.hiwire.new_value(value);
      let errcode;
      try {
        errcode = __pyproxy_setitem(ptrobj, idkey, idval);
      } catch (e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
        Module.hiwire.decref(idval);
      }
      if (errcode === -1) {
        _pythonexc2js();
      }
    },
    delete : function(key) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let errcode;
      try {
        errcode = __pyproxy_delitem(ptrobj, idkey);
      } catch (e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if (errcode === -1) {
        _pythonexc2js();
      }
    }
  };

  // Controlled by HAS_CONTAINS flag, appears for any class with __contains__ or
  // sq_contains
  Module.PyProxyContainsMethods = {
    has : function(key) {
      let ptrobj = _getPtr(this);
      let idkey = Module.hiwire.new_value(key);
      let result;
      try {
        result = __pyproxy_contains(ptrobj, idkey);
      } catch (e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idkey);
      }
      if (result === -1) {
        _pythonexc2js();
      }
      return result === 1;
    },
  };

  /**
   * A helper for [Symbol.iterator].
   *
   * Because "it is possible for a generator to be garbage collected without
   * ever running its finally block", we take extra care to try to ensure that
   * we don't leak the iterator. We register it with the finalizationRegistry,
   * but if the finally block is executed, we decref the pointer and unregister.
   *
   * In order to do this, we create the generator with this inner method,
   * register the finalizer, and then return it.
   *
   * Quote from:
   * https://hacks.mozilla.org/2015/07/es6-in-depth-generators-continued/
   *
   * @private
   */
  function* iter_helper(iterptr, token) {
    try {
      if (iterptr === 0) {
        pythonexc2js();
      }
      let item;
      while ((item = __pyproxy_iter_next(iterptr))) {
        yield Module.hiwire.pop_value(item);
      }
      if (_PyErr_Occurred()) {
        pythonexc2js();
      }
    } finally {
      finalizationRegistry.unregister(token);
      _Py_DecRef(iterptr);
    }
  }

  // Controlled by IS_ITERABLE, appears for any object with __iter__ or tp_iter,
  // unless they are iterators. See: https://docs.python.org/3/c-api/iter.html
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols
  // This avoids allocating a PyProxy wrapper for the temporary iterator.
  Module.PyProxyIterableMethods = {
    [Symbol.iterator] : function() {
      let token = {};
      let iterptr = _PyObject_GetIter(_getPtr(this));
      let result = iter_helper(iterptr, token);
      Module.finalizationRegistry.register(result, iterptr, token);
      return result;
    },
  };

  // Controlled by IS_ITERATOR, appears for any object with a __next__ or
  // tp_iternext method.
  Module.PyProxyIteratorMethods = {
    [Symbol.iterator] : function() { return this; },
    next : function(arg) {
      let idresult;
      // Note: arg is optional, if arg is not supplied, it will be undefined
      // which gets converted to "Py_None". This is as intended.
      let idarg = Module.hiwire.new_value(arg);
      try {
        idresult = __pyproxyGen_Send(_getPtr(this), idarg);
      } catch (e) {
        Module.fatal_error(e);
      } finally {
        Module.hiwire.decref(idarg);
      }

      let done = false;
      if (idresult === 0) {
        idresult = __pyproxyGen_FetchStopIterationValue();
        if (idresult) {
          done = true;
        } else {
          _pythonexc2js();
        }
      }
      let value = Module.hiwire.pop_value(idresult);
      return {done, value};
    },
  };

  // Another layer of boilerplate. The PyProxyHandlers have some annoying logic
  // to deal with straining out the spurious "Function" properties "prototype",
  // "arguments", and "length", to deal with correctly satisfying the Proxy
  // invariants, and to deal with the mro
  function python_hasattr(jsobj, jskey) {
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let result;
    try {
      result = __pyproxy_hasattr(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (result === -1) {
      _pythonexc2js();
    }
    return result !== 0;
  }

  // Returns a JsRef in order to allow us to differentiate between "not found"
  // (in which case we return 0) and "found 'None'" (in which case we return
  // Js_undefined).
  function python_getattr(jsobj, jskey) {
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let idresult;
    try {
      idresult = __pyproxy_getattr(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (idresult === 0) {
      if (_PyErr_Occurred()) {
        _pythonexc2js();
      }
    }
    return idresult;
  }

  function python_setattr(jsobj, jskey, jsval) {
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let idval = Module.hiwire.new_value(jsval);
    let errcode;
    try {
      errcode = __pyproxy_setattr(ptrobj, idkey, idval);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
    }
    if (errcode === -1) {
      _pythonexc2js();
    }
  }

  function python_delattr(jsobj, jskey) {
    let ptrobj = _getPtr(jsobj);
    let idkey = Module.hiwire.new_value(jskey);
    let errcode;
    try {
      errcode = __pyproxy_delattr(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (errcode === -1) {
      _pythonexc2js();
    }
  }

  // See explanation of which methods should be defined here and what they do
  // here:
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
  Module.PyProxyHandlers = {
    isExtensible : function() { return true },
    has : function(jsobj, jskey) {
      // Note: must report "prototype" in proxy when we are callable.
      // (We can return the wrong value from "get" handler though.)
      let objHasKey = Reflect.has(jsobj, jskey);
      if (objHasKey) {
        return true;
      }
      // python_hasattr will crash when given a Symbol.
      if (typeof (jskey) === "symbol") {
        return false;
      }
      return python_hasattr(jsobj, jskey);
    },
    get : function(jsobj, jskey) {
      // Preference order:
      // 1. things we have to return to avoid making Javascript angry
      // 2. the result of Python getattr
      // 3. stuff from the prototype chain

      // 1. things we have to return to avoid making Javascript angry
      // This conditional looks funky but it's the only thing I found that
      // worked right in all cases.
      if ((jskey in jsobj) && !(jskey in Object.getPrototypeOf(jsobj))) {
        return Reflect.get(jsobj, jskey);
      }
      // python_getattr will crash when given a Symbol
      if (typeof (jskey) === "symbol") {
        return Reflect.get(jsobj, jskey);
      }
      // 2. The result of getattr
      let idresult = python_getattr(jsobj, jskey);
      if (idresult !== 0) {
        return Module.hiwire.pop_value(idresult);
      }
      // 3. stuff from the prototype chain.
      return Reflect.get(jsobj, jskey);
    },
    set : function(jsobj, jskey, jsval) {
      // We're only willing to set properties on the python object, throw an
      // error if user tries to write over any key of type 1. things we have to
      // return to avoid making Javascript angry
      if (typeof (jskey) === "symbol") {
        throw new TypeError(
            `Cannot set read only field '${jskey.description}'`);
      }
      // Again this is a funny looking conditional, I found it as the result of
      // a lengthy search for something that worked right.
      let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
      if (descr && !descr.writable) {
        throw new TypeError(`Cannot set read only field '${jskey}'`);
      }
      python_setattr(jsobj, jskey, jsval);
      return true;
    },
    deleteProperty : function(jsobj, jskey) {
      // We're only willing to delete properties on the python object, throw an
      // error if user tries to write over any key of type 1. things we have to
      // return to avoid making Javascript angry
      if (typeof (jskey) === "symbol") {
        throw new TypeError(
            `Cannot delete read only field '${jskey.description}'`);
      }
      let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
      if (descr && !descr.writable) {
        throw new TypeError(`Cannot delete read only field '${jskey}'`);
      }
      python_delattr(jsobj, jskey);
      // Must return "false" if "jskey" is a nonconfigurable own property.
      // Otherwise Javascript will throw a TypeError.
      return !descr || descr.configurable;
    },
    ownKeys : function(jsobj) {
      let ptrobj = _getPtr(jsobj);
      let idresult;
      try {
        idresult = __pyproxy_ownKeys(ptrobj);
      } catch (e) {
        Module.fatal_error(e);
      }
      let result = Module.hiwire.pop_value(idresult);
      result.push(...Reflect.ownKeys(jsobj));
      return result;
    },
    // clang-format off
    apply : function(jsobj, jsthis, jsargs) {
      return jsobj.apply(jsthis, jsargs);
    },
    // clang-format on
  };

  /**
   * The Promise / javascript awaitable API.
   */
  Module.PyProxyAwaitableMethods = {
    /**
     * This wraps __pyproxy_ensure_future and makes a function that converts a
     * Python awaitable to a promise, scheduling the awaitable on the Python
     * event loop if necessary.
     */
    _ensure_future : function() {
      let resolve_handle_id = 0;
      let reject_handle_id = 0;
      let resolveHandle;
      let rejectHandle;
      let promise;
      try {
        promise = new Promise((resolve, reject) => {
          resolveHandle = resolve;
          rejectHandle = reject;
        });
        resolve_handle_id = Module.hiwire.new_value(resolveHandle);
        reject_handle_id = Module.hiwire.new_value(rejectHandle);
        let ptrobj = _getPtr(this);
        let errcode = __pyproxy_ensure_future(ptrobj, resolve_handle_id,
                                              reject_handle_id);
        if (errcode === -1) {
          _pythonexc2js();
        }
      } finally {
        Module.hiwire.decref(resolve_handle_id);
        Module.hiwire.decref(reject_handle_id);
      }
      return promise;
    },
    then : function(onFulfilled, onRejected) {
      let promise = this._ensure_future();
      return promise.then(onFulfilled, onRejected);
    },
    catch : function(onRejected) {
      let promise = this._ensure_future();
      return promise.catch(onRejected);
    },
    finally : function(onFinally) {
      let promise = this._ensure_future();
      return promise.finally(onFinally);
    }
  };

  Module.PyProxyCallableMethods = {prototype : Function.prototype};
  Module.PyProxyBufferMethods = {};

  // A special proxy that we use to wrap pyodide.globals to allow property
  // access like `pyodide.globals.x`.
  let globalsPropertyAccessWarned = false;
  let globalsPropertyAccessWarningMsg =
      "Access to pyodide.globals via pyodide.globals.key is deprecated and " +
      "will be removed in version 0.18.0. Use pyodide.globals.get('key'), " +
      "pyodide.globals.set('key', value), pyodide.globals.delete('key') instead.";
  let NamespaceProxyHandlers = {
    // clang-format off
    has : function(obj, key) {
      return Reflect.has(obj, key) || obj.has(key);
    },
    // clang-format on
    get : function(obj, key) {
      if (Reflect.has(obj, key)) {
        return Reflect.get(obj, key);
      }
      let result = obj.get(key);
      if (!globalsPropertyAccessWarned && result !== undefined) {
        console.warn(globalsPropertyAccessWarningMsg);
        globalsPropertyAccessWarned = true;
      }
      return result;
    },
    set : function(obj, key, value) {
      if (Reflect.has(obj, key)) {
        throw new Error(`Cannot set read only field ${key}`);
      }
      if (!globalsPropertyAccessWarned) {
        globalsPropertyAccessWarned = true;
        console.warn(globalsPropertyAccessWarningMsg);
      }
      obj.set(key, value);
    },
    ownKeys : function(obj) {
      let result = new Set(Reflect.ownKeys(obj));
      let iter = obj.keys();
      for (let key of iter) {
        result.add(key);
      }
      iter.destroy();
      return Array.from(result);
    }
  };

  // clang-format off
  Module.wrapNamespace = function wrapNamespace(ns) {
    return new Proxy(ns, NamespaceProxyHandlers);
  };
  // clang-format on
  return 0;
});
