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
TEMP_EMJS_HELPER(() => {0, /* Magic, see comment */
  Module.PyProxies = {};
  // clang-format on

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
   * @private
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
    /**
     * The name of the type of the object.
     *
     * Usually the value is ``"module.name"`` but for builtins or
     * interpreter-defined types it is just ``"name"``. As pseudocode this is:
     *
     * .. code-block:: python
     *
     *    ty = type(x)
     *    if ty.__module__ == 'builtins' or ty.__module__ == "__main__":
     *        return ty.__name__
     *    else:
     *        ty.__module__ + "." + ty.__name__
     *
     */
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
    /**
     * Destroy the ``PyProxy``. This will release the memory. Any further
     * attempt to use the object will raise an error.
     *
     * In a browser supporting `FinalizationRegistry
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/FinalizationRegistry>`_
     * Pyodide will automatically destroy the ``PyProxy`` when it is garbage
     * collected, however there is no guarantee that the finalizer will be run
     * in a timely manner so it is better to ``destory`` the proxy explicitly.
     */
    destroy() {
      let ptrobj = _getPtr(this);
      __pyproxy_destroy(ptrobj);
      this.$$.ptr = null;
    }
    /**
     * Converts the ``PyProxy`` into a Javascript object as best as possible. By
     * default does a deep conversion, if a shallow conversion is desired, you
     * can use ``proxy.toJs(1)``.
     * See :ref:`Explicit Conversion of PyProxy
     * <type-translations-pyproxy-to-js>` for more info.
     *
     * @param {number} depth How many layers deep to perform the conversion.
     * Defaults to infinite.
     * @returns The Javascript object resulting from the conversion.
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
    /**
     * The length of the object.
     *
     * Present only if ``type(obj)`` has a `__len__` method.
     */
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
    /**
     * This translates to the Python code ``obj[key]``.
     *
     * Present only if ``type(obj)`` has a ``__getitem__`` method.
     *
     * @param {any} key The key to look up.
     * @returns The corresponding value.
     */
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
    /**
     * This translates to the Python code ``obj[key] = value``.
     *
     * Present only if ``type(obj)`` has a ``__setitem__`` method.
     *
     * @param {any} key The key to set.
     * @param {any} value The value to set it to.
     */
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
    /**
     * This translates to the Python code ``del obj[key]``.
     *
     * Present only if ``type(obj)`` has a ``__delitem__`` method.
     *
     * @param {any} key The key to delete.
     */
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
    /**
     * This translates to the Python code ``key in obj``.
     *
     * Present only if ``type(obj)`` has a ``__contains__`` method.
     *
     * @param {*} key The key to check for.
     * @returns {bool} Is ``key`` present?
     */
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

  // Controlled by IS_ITERABLE, appears for any object with __iter__ or tp_iter,
  // unless they are iterators. See: https://docs.python.org/3/c-api/iter.html
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols
  // This avoids allocating a PyProxy wrapper for the temporary iterator.
  Module.PyProxyIterableMethods = {
    /**
     * This translates to the Python code ``iter(obj)``. Return an iterator
     * associated to the proxy. See the documentation for `Symbol.iterator
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol/iterator>`_.
     *
     * Present only if the Python object is iterable (i.e., ``type(obj)`` has an
     * ``__iter__`` method).
     *
     * This will be used implicitly by ``for(let x of proxy){}``.
     *
     * @returns {Iterator} An iterator for ``obj``.
     */
    [Symbol.iterator] : function*() {
      let iterptr = _PyObject_GetIter(_getPtr(this));
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
      _Py_DecRef(iterptr);
    }
  };

  // Controlled by IS_ITERATOR, appears for any object with a __next__ or
  // tp_iternext method.
  Module.PyProxyIteratorMethods = {
    [Symbol.iterator] : function() { return this; },
    /**
     * This translates to the Python code ``next(obj)``. Returns the next value
     * of the generator. See the documentation for `Generator.prototype.next
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Generator/next>`_.
     * The argument will be sent to the Python generator.
     *
     * This will be used implicitly by ``for(let x of proxy){}``.
     *
     * Present only if ``obj`` is a Python generator or iterator (i.e.,
     * ``type(obj)`` has an ``__iter__`` method).
     *
     * @param {*} value The value to send to the generator. The value will be
     * assigned as a result of a yield expression.
     * @returns {Object} An Object with two properties, ``done`` and ``value``.
     * If the generator returned ``some_value``, will return ``{done : false,
     * value : some_value}``. If the Python generator raised a
     * ``StopIteration(result_value)`` exception, then we return ``{done : true,
     * value : result_value}``.
     */
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
   * @private
   */
  Module.PyProxyAwaitableMethods = {
    /**
     * This wraps __pyproxy_ensure_future and makes a function that converts a
     * Python awaitable to a promise, scheduling the awaitable on the Python
     * event loop if necessary.
     * @private
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
    /**
     * Runs ``asyncio.ensure_future(awaitable)``, executes
     * ``onFulfilled(result)`` when the ``Future`` resolves successfully,
     * executes ``onRejected(error)`` when the ``Future`` fails. Will be used
     * implictly by ``await obj``.
     *
     * See the documentation for
     * `Promise.then
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/then>`_
     *
     * Only present on awaitable Python objects.
     *
     * @param {Function} onFulfilled A handler called with the result as an
     * argument if the awaitable succeeds.
     * @param {Function} onRejected A handler called with the error as an
     * argument if the awaitable fails.
     * @returns {Promise} The resulting Promise.
     */
    then : function(onFulfilled, onRejected) {
      let promise = this._ensure_future();
      return promise.then(onFulfilled, onRejected);
    },
    /**
     * Runs ``asyncio.ensure_future(awaitable)`` and executes
     * ``onRejected(error)`` if the future fails.
     *
     * See the documentation for
     * `Promise.catch
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/catch>`_.
     *
     * Only present on awaitable Python objects.
     *
     * @param {Function} onRejected A handler called with the error as an
     * argument if the awaitable fails.
     * @returns {Promise} The resulting Promise.
     */
    catch : function(onRejected) {
      let promise = this._ensure_future();
      return promise.catch(onRejected);
    },
    /**
     * Runs ``asyncio.ensure_future(awaitable)`` and executes
     * ``onFinally(error)`` when the future resolves.
     *
     * See the documentation for
     * `Promise.finally
     * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/finally>`_.
     *
     * Only present on `awaitable
     * <https://docs.python.org/3/library/asyncio-task.html?highlight=awaitable#awaitables>`_
     * Python objects.
     *
     * @param {Function} onFinally A handler that is called with zero arguments
     * when the awaitable resolves.
     * @returns {Promise} A Promise that resolves or rejects with the same
     * result as the original Promise, but only after executing the
     * ``onFinally`` handler.
     */
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
