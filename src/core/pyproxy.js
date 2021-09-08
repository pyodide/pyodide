/**
 * Every public Python entrypoint goes through this file! The main entrypoint is
 * the callPyObject method, but of course one can also execute arbitrary code
 * via the various __dundermethods__ associated to classes.
 *
 * The only entrypoint into Python that avoids this file is our bootstrap method
 * runPythonSimple which is defined in main.c
 *
 * Any time we call into wasm, the call should be wrapped in a try catch block.
 * This way if a Javascript error emerges from the wasm, we can escalate it to a
 * fatal error.
 *
 * This is file is preprocessed with -imacros "pyproxy.c". As a result of this,
 * any macros available in pyproxy.c are available here. We only need the flags
 * macros HAS_LENGTH, etc.
 *
 * See Makefile recipe for src/js/pyproxy.js
 */

import { Module } from "./module.js";

/**
 * Is the argument a :any:`PyProxy`?
 * @param jsobj {any} Object to test.
 * @returns {jsobj is PyProxy} Is ``jsobj`` a :any:`PyProxy`?
 */
export function isPyProxy(jsobj) {
  return !!jsobj && jsobj.$$ !== undefined && jsobj.$$.type === "PyProxy";
}
Module.isPyProxy = isPyProxy;

if (globalThis.FinalizationRegistry) {
  Module.finalizationRegistry = new FinalizationRegistry(([ptr, cache]) => {
    pyproxy_decref_cache(cache);
    try {
      Module._Py_DecRef(ptr);
    } catch (e) {
      // I'm not really sure what happens if an error occurs inside of a
      // finalizer...
      Module.fatal_error(e);
    }
  });
  // For some unclear reason this code screws up selenium FirefoxDriver. Works
  // fine in chrome and when I test it in browser. It seems to be sensitive to
  // changes that don't make a difference to the semantics.
  // TODO: after 0.18.0, fix selenium issues with this code.
  // Module.bufferFinalizationRegistry = new FinalizationRegistry((ptr) => {
  //   try {
  //     Module._PyBuffer_Release(ptr);
  //     Module._PyMem_Free(ptr);
  //   } catch (e) {
  //     Module.fatal_error(e);
  //   }
  // });
} else {
  Module.finalizationRegistry = { register() {}, unregister() {} };
  // Module.bufferFinalizationRegistry = finalizationRegistry;
}

let pyproxy_alloc_map = new Map();
Module.pyproxy_alloc_map = pyproxy_alloc_map;
let trace_pyproxy_alloc;
let trace_pyproxy_dealloc;

Module.enable_pyproxy_allocation_tracing = function () {
  trace_pyproxy_alloc = function (proxy) {
    pyproxy_alloc_map.set(proxy, Error().stack);
  };
  trace_pyproxy_dealloc = function (proxy) {
    pyproxy_alloc_map.delete(proxy);
  };
};
Module.disable_pyproxy_allocation_tracing = function () {
  trace_pyproxy_alloc = function (proxy) {};
  trace_pyproxy_dealloc = function (proxy) {};
};
Module.disable_pyproxy_allocation_tracing();

/**
 * Create a new PyProxy wraping ptrobj which is a PyObject*.
 *
 * The argument cache is only needed to implement the PyProxy.copy API, it
 * allows the copy of the PyProxy to share its attribute cache with the original
 * version. In all other cases, pyproxy_new should be called with one argument.
 *
 * In the case that the Python object is callable, PyProxyClass inherits from
 * Function so that PyProxy objects can be callable. In that case we MUST expose
 * certain properties inherited from Function, but we do our best to remove as
 * many as possible.
 * @private
 */
Module.pyproxy_new = function (ptrobj, cache) {
  let flags = Module._pyproxy_getflags(ptrobj);
  let cls = Module.getPyProxyClass(flags);
  // Reflect.construct calls the constructor of Module.PyProxyClass but sets
  // the prototype as cls.prototype. This gives us a way to dynamically create
  // subclasses of PyProxyClass (as long as we don't need to use the "new
  // cls(ptrobj)" syntax).
  let target;
  if (flags & IS_CALLABLE) {
    // To make a callable proxy, we must call the Function constructor.
    // In this case we are effectively subclassing Function.
    target = Reflect.construct(Function, [], cls);
    // Remove undesirable properties added by Function constructor. Note: we
    // can't remove "arguments" or "caller" because they are not configurable
    // and not writable
    delete target.length;
    delete target.name;
    // prototype isn't configurable so we can't delete it but it's writable.
    target.prototype = undefined;
  } else {
    target = Object.create(cls.prototype);
  }
  if (!cache) {
    // The cache needs to be accessed primarily from the C function
    // _pyproxy_getattr so we make a hiwire id.
    let cacheId = Module.hiwire.new_value(new Map());
    cache = { cacheId, refcnt: 0 };
  }
  cache.refcnt++;
  Object.defineProperty(target, "$$", {
    value: { ptr: ptrobj, type: "PyProxy", borrowed: false, cache },
  });
  Module._Py_IncRef(ptrobj);
  let proxy = new Proxy(target, PyProxyHandlers);
  trace_pyproxy_alloc(proxy);
  Module.finalizationRegistry.register(proxy, [ptrobj, cache], proxy);
  return proxy;
};

function _getPtr(jsobj) {
  let ptr = jsobj.$$.ptr;
  if (ptr === null) {
    throw new Error(
      jsobj.$$.destroyed_msg || "Object has already been destroyed"
    );
  }
  return ptr;
}

let pyproxyClassMap = new Map();
/**
 * Retreive the appropriate mixins based on the features requested in flags.
 * Used by pyproxy_new. The "flags" variable is produced by the C function
 * pyproxy_getflags. Multiple PyProxies with the same set of feature flags
 * will share the same prototype, so the memory footprint of each individual
 * PyProxy is minimal.
 * @private
 */
Module.getPyProxyClass = function (flags) {
  let result = pyproxyClassMap.get(flags);
  if (result) {
    return result;
  }
  let descriptors = {};
  for (let [feature_flag, methods] of [
    [HAS_LENGTH, PyProxyLengthMethods],
    [HAS_GET, PyProxyGetItemMethods],
    [HAS_SET, PyProxySetItemMethods],
    [HAS_CONTAINS, PyProxyContainsMethods],
    [IS_ITERABLE, PyProxyIterableMethods],
    [IS_ITERATOR, PyProxyIteratorMethods],
    [IS_AWAITABLE, PyProxyAwaitableMethods],
    [IS_BUFFER, PyProxyBufferMethods],
    [IS_CALLABLE, PyProxyCallableMethods],
  ]) {
    if (flags & feature_flag) {
      Object.assign(
        descriptors,
        Object.getOwnPropertyDescriptors(methods.prototype)
      );
    }
  }
  // Use base constructor (just throws an error if construction is attempted).
  descriptors.constructor = Object.getOwnPropertyDescriptor(
    PyProxyClass.prototype,
    "constructor"
  );
  Object.assign(
    descriptors,
    Object.getOwnPropertyDescriptors({ $$flags: flags })
  );
  let new_proto = Object.create(PyProxyClass.prototype, descriptors);
  function NewPyProxyClass() {}
  NewPyProxyClass.prototype = new_proto;
  pyproxyClassMap.set(flags, NewPyProxyClass);
  return NewPyProxyClass;
};

// Static methods
Module.PyProxy_getPtr = _getPtr;
Module.pyproxy_mark_borrowed = function (proxy) {
  proxy.$$.borrowed = true;
};

const pyproxy_cache_destroyed_msg =
  "This borrowed attribute proxy was automatically destroyed in the " +
  "process of destroying the proxy it was borrowed from. Try using the 'copy' method.";

function pyproxy_decref_cache(cache) {
  if (!cache) {
    return;
  }
  cache.refcnt--;
  if (cache.refcnt === 0) {
    let cache_map = Module.hiwire.pop_value(cache.cacheId);
    for (let proxy_id of cache_map.values()) {
      Module.pyproxy_destroy(
        Module.hiwire.pop_value(proxy_id),
        pyproxy_cache_destroyed_msg
      );
    }
  }
}

Module.pyproxy_destroy = function (proxy, destroyed_msg) {
  let ptrobj = _getPtr(proxy);
  Module.finalizationRegistry.unregister(proxy);
  // Maybe the destructor will call Javascript code that will somehow try
  // to use this proxy. Mark it deleted before decrementing reference count
  // just in case!
  proxy.$$.ptr = null;
  proxy.$$.destroyed_msg = destroyed_msg;
  pyproxy_decref_cache(proxy.$$.cache);
  try {
    Module._Py_DecRef(ptrobj);
    trace_pyproxy_dealloc(proxy);
  } catch (e) {
    Module.fatal_error(e);
  }
};

// Now a lot of boilerplate to wrap the abstract Object protocol wrappers
// defined in pyproxy.c in Javascript functions.

Module.callPyObjectKwargs = function (ptrobj, ...jsargs) {
  // We don't do any checking for kwargs, checks are in PyProxy.callKwargs
  // which only is used when the keyword arguments come from the user.
  let kwargs = jsargs.pop();
  let num_pos_args = jsargs.length;
  let kwargs_names = Object.keys(kwargs);
  let kwargs_values = Object.values(kwargs);
  let num_kwargs = kwargs_names.length;
  jsargs.push(...kwargs_values);

  let idargs = Module.hiwire.new_value(jsargs);
  let idkwnames = Module.hiwire.new_value(kwargs_names);
  let idresult;
  try {
    idresult = Module.__pyproxy_apply(
      ptrobj,
      idargs,
      num_pos_args,
      idkwnames,
      num_kwargs
    );
  } catch (e) {
    Module.fatal_error(e);
  } finally {
    Module.hiwire.decref(idargs);
    Module.hiwire.decref(idkwnames);
  }
  if (idresult === 0) {
    Module._pythonexc2js();
  }
  return Module.hiwire.pop_value(idresult);
};

Module.callPyObject = function (ptrobj, ...jsargs) {
  return Module.callPyObjectKwargs(ptrobj, ...jsargs, {});
};

/**
 * @typedef {(PyProxyClass & {[x : string] : Py2JsResult})} PyProxy
 * @typedef { PyProxy | number | bigint | string | boolean | undefined } Py2JsResult
 */
class PyProxyClass {
  constructor() {
    throw new TypeError("PyProxy is not a constructor");
  }

  get [Symbol.toStringTag]() {
    return "PyProxy";
  }
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
   * @type {string}
   */
  get type() {
    let ptrobj = _getPtr(this);
    return Module.hiwire.pop_value(Module.__pyproxy_type(ptrobj));
  }
  /**
   * @returns {string}
   */
  toString() {
    let ptrobj = _getPtr(this);
    let jsref_repr;
    try {
      jsref_repr = Module.__pyproxy_repr(ptrobj);
    } catch (e) {
      Module.fatal_error(e);
    }
    if (jsref_repr === 0) {
      Module._pythonexc2js();
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
   * in a timely manner so it is better to ``destroy`` the proxy explicitly.
   *
   * @param {string} [destroyed_msg] The error message to print if use is
   *        attempted after destroying. Defaults to "Object has already been
   *        destroyed".
   */
  destroy(destroyed_msg) {
    if (!this.$$.borrowed) {
      Module.pyproxy_destroy(this, destroyed_msg);
    }
  }
  /**
   * Make a new PyProxy pointing to the same Python object.
   * Useful if the PyProxy is destroyed somewhere else.
   * @returns {PyProxy}
   */
  copy() {
    let ptrobj = _getPtr(this);
    return Module.pyproxy_new(ptrobj, this.$$.cache);
  }
  /**
   * Converts the ``PyProxy`` into a Javascript object as best as possible. By
   * default does a deep conversion, if a shallow conversion is desired, you can
   * use ``proxy.toJs({depth : 1})``. See :ref:`Explicit Conversion of PyProxy
   * <type-translations-pyproxy-to-js>` for more info.
   *
   * @param {object} options
   * @param {number} [options.depth] How many layers deep to perform the
   * conversion. Defaults to infinite.
   * @param {array} [options.pyproxies] If provided, ``toJs`` will store all
   * PyProxies created in this list. This allows you to easily destroy all the
   * PyProxies by iterating the list without having to recurse over the
   * generated structure. The most common use case is to create a new empty
   * list, pass the list as `pyproxies`, and then later iterate over `pyproxies`
   * to destroy all of created proxies.
   * @param {bool} [options.create_pyproxies] If false, ``toJs`` will throw a
   * ``ConversionError`` rather than producing a ``PyProxy``.
   * @param {bool} [options.dict_converter] A function to be called on an
   * iterable of pairs ``[key, value]``. Convert this iterable of pairs to the
   * desired output. For instance, ``Object.fromEntries`` would convert the dict
   * to an object, ``Array.from`` converts it to an array of entries, and ``(it) =>
   * new Map(it)`` converts it to a ``Map`` (which is the default behavior).
   * @return {any} The Javascript object resulting from the conversion.
   */
  toJs({
    depth = -1,
    pyproxies,
    create_pyproxies = true,
    dict_converter,
  } = {}) {
    let ptrobj = _getPtr(this);
    let idresult;
    let proxies_id;
    let dict_converter_id = 0;
    if (!create_pyproxies) {
      proxies_id = 0;
    } else if (pyproxies) {
      proxies_id = Module.hiwire.new_value(pyproxies);
    } else {
      proxies_id = Module.hiwire.new_value([]);
    }
    if (dict_converter) {
      dict_converter_id = Module.hiwire.new_value(dict_converter);
    }
    try {
      idresult = Module._python2js_custom_dict_converter(
        ptrobj,
        depth,
        proxies_id,
        dict_converter_id
      );
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(proxies_id);
      Module.hiwire.decref(dict_converter_id);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    return Module.hiwire.pop_value(idresult);
  }
  /**
   * Check whether the :any:`PyProxy.length` getter is available on this PyProxy. A
   * Typescript type guard.
   * @returns {this is PyProxyWithLength}
   */
  supportsLength() {
    return !!(this.$$flags & HAS_LENGTH);
  }
  /**
   * Check whether the :any:`PyProxy.get` method is available on this PyProxy. A
   * Typescript type guard.
   * @returns {this is PyProxyWithGet}
   */
  supportsGet() {
    return !!(this.$$flags & HAS_GET);
  }
  /**
   * Check whether the :any:`PyProxy.set` method is available on this PyProxy. A
   * Typescript type guard.
   * @returns {this is PyProxyWithSet}
   */
  supportsSet() {
    return !!(this.$$flags & HAS_SET);
  }
  /**
   * Check whether the :any:`PyProxy.has` method is available on this PyProxy. A
   * Typescript type guard.
   * @returns {this is PyProxyWithHas}
   */
  supportsHas() {
    return !!(this.$$flags & HAS_CONTAINS);
  }
  /**
   * Check whether the PyProxy is iterable. A Typescript type guard for
   * :any:`PyProxy.[Symbol.iterator]`.
   * @returns {this is PyProxyIterable}
   */
  isIterable() {
    return !!(this.$$flags & (IS_ITERABLE | IS_ITERATOR));
  }
  /**
   * Check whether the PyProxy is iterable. A Typescript type guard for
   * :any:`PyProxy.next`.
   * @returns {this is PyProxyIterator}
   */
  isIterator() {
    return !!(this.$$flags & IS_ITERATOR);
  }
  /**
   * Check whether the PyProxy is awaitable. A Typescript type guard, if this
   * function returns true Typescript considers the PyProxy to be a ``Promise``.
   * @returns {this is PyProxyAwaitable}
   */
  isAwaitable() {
    return !!(this.$$flags & IS_AWAITABLE);
  }
  /**
   * Check whether the PyProxy is a buffer. A Typescript type guard for
   * :any:`PyProxy.getBuffer`.
   * @returns {this is PyProxyBuffer}
   */
  isBuffer() {
    return !!(this.$$flags & IS_BUFFER);
  }
  /**
   * Check whether the PyProxy is a Callable. A Typescript type guard, if this
   * returns true then Typescript considers the Proxy to be callable of
   * signature ``(args... : any[]) => PyProxy | number | bigint | string |
   * boolean | undefined``.
   * @returns {this is PyProxyCallable}
   */
  isCallable() {
    return !!(this.$$flags & IS_CALLABLE);
  }
}

/**
 * @typedef { PyProxy & PyProxyLengthMethods } PyProxyWithLength
 */
// Controlled by HAS_LENGTH, appears for any object with __len__ or sq_length
// or mp_length methods
class PyProxyLengthMethods {
  /**
   * The length of the object.
   *
   * Present only if the proxied Python object has a ``__len__`` method.
   * @returns {number}
   */
  get length() {
    let ptrobj = _getPtr(this);
    let length;
    try {
      length = Module._PyObject_Size(ptrobj);
    } catch (e) {
      Module.fatal_error(e);
    }
    if (length === -1) {
      Module._pythonexc2js();
    }
    return length;
  }
}

/**
 * @typedef {PyProxy & PyProxyGetItemMethods} PyProxyWithGet
 */

// Controlled by HAS_GET, appears for any class with __getitem__,
// mp_subscript, or sq_item methods
/**
 * @interface
 */
class PyProxyGetItemMethods {
  /**
   * This translates to the Python code ``obj[key]``.
   *
   * Present only if the proxied Python object has a ``__getitem__`` method.
   *
   * @param {any} key The key to look up.
   * @returns {Py2JsResult} The corresponding value.
   */
  get(key) {
    let ptrobj = _getPtr(this);
    let idkey = Module.hiwire.new_value(key);
    let idresult;
    try {
      idresult = Module.__pyproxy_getitem(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (idresult === 0) {
      if (Module._PyErr_Occurred()) {
        Module._pythonexc2js();
      } else {
        return undefined;
      }
    }
    return Module.hiwire.pop_value(idresult);
  }
}

/**
 * @typedef {PyProxy & PyProxySetItemMethods} PyProxyWithSet
 */
// Controlled by HAS_SET, appears for any class with __setitem__, __delitem__,
// mp_ass_subscript,  or sq_ass_item.
class PyProxySetItemMethods {
  /**
   * This translates to the Python code ``obj[key] = value``.
   *
   * Present only if the proxied Python object has a ``__setitem__`` method.
   *
   * @param {any} key The key to set.
   * @param {any} value The value to set it to.
   */
  set(key, value) {
    let ptrobj = _getPtr(this);
    let idkey = Module.hiwire.new_value(key);
    let idval = Module.hiwire.new_value(value);
    let errcode;
    try {
      errcode = Module.__pyproxy_setitem(ptrobj, idkey, idval);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
      Module.hiwire.decref(idval);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
  }
  /**
   * This translates to the Python code ``del obj[key]``.
   *
   * Present only if the proxied Python object has a ``__delitem__`` method.
   *
   * @param {any} key The key to delete.
   */
  delete(key) {
    let ptrobj = _getPtr(this);
    let idkey = Module.hiwire.new_value(key);
    let errcode;
    try {
      errcode = Module.__pyproxy_delitem(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
  }
}

/**
 * @typedef {PyProxy & PyProxyContainsMethods} PyProxyWithHas
 */

// Controlled by HAS_CONTAINS flag, appears for any class with __contains__ or
// sq_contains
class PyProxyContainsMethods {
  /**
   * This translates to the Python code ``key in obj``.
   *
   * Present only if the proxied Python object has a ``__contains__`` method.
   *
   * @param {*} key The key to check for.
   * @returns {boolean} Is ``key`` present?
   */
  has(key) {
    let ptrobj = _getPtr(this);
    let idkey = Module.hiwire.new_value(key);
    let result;
    try {
      result = Module.__pyproxy_contains(ptrobj, idkey);
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idkey);
    }
    if (result === -1) {
      Module._pythonexc2js();
    }
    return result === 1;
  }
}

class TempError extends Error {}

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
      throw new TempError();
    }
    let item;
    while ((item = Module.__pyproxy_iter_next(iterptr))) {
      yield Module.hiwire.pop_value(item);
    }
    if (Module._PyErr_Occurred()) {
      throw new TempError();
    }
  } catch (e) {
    if (e instanceof TempError) {
      Module._pythonexc2js();
    } else {
      Module.fatal_error(e);
    }
  } finally {
    Module.finalizationRegistry.unregister(token);
    Module._Py_DecRef(iterptr);
  }
}

/**
 * @typedef {PyProxy & PyProxyIterableMethods} PyProxyIterable
 */

// Controlled by IS_ITERABLE, appears for any object with __iter__ or tp_iter,
// unless they are iterators. See: https://docs.python.org/3/c-api/iter.html
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols
// This avoids allocating a PyProxy wrapper for the temporary iterator.
class PyProxyIterableMethods {
  /**
   * This translates to the Python code ``iter(obj)``. Return an iterator
   * associated to the proxy. See the documentation for `Symbol.iterator
   * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol/iterator>`_.
   *
   * Present only if the proxied Python object is iterable (i.e., has an
   * ``__iter__`` method).
   *
   * This will be used implicitly by ``for(let x of proxy){}``.
   *
   * @returns {Iterator<Py2JsResult, Py2JsResult, any>} An iterator for the proxied Python object.
   */
  [Symbol.iterator]() {
    let ptrobj = _getPtr(this);
    let token = {};
    let iterptr;
    try {
      iterptr = Module._PyObject_GetIter(ptrobj);
    } catch (e) {
      Module.fatal_error(e);
    }

    let result = iter_helper(iterptr, token);
    Module.finalizationRegistry.register(result, [iterptr, undefined], token);
    return result;
  }
}

/**
 * @typedef {PyProxy & PyProxyIteratorMethods} PyProxyIterator
 */

// Controlled by IS_ITERATOR, appears for any object with a __next__ or
// tp_iternext method.
class PyProxyIteratorMethods {
  [Symbol.iterator]() {
    return this;
  }
  /**
   * This translates to the Python code ``next(obj)``. Returns the next value
   * of the generator. See the documentation for `Generator.prototype.next
   * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Generator/next>`_.
   * The argument will be sent to the Python generator.
   *
   * This will be used implicitly by ``for(let x of proxy){}``.
   *
   * Present only if the proxied Python object is a generator or iterator
   * (i.e., has a ``send`` or ``__next__`` method).
   *
   * @param {any=} [value] The value to send to the generator. The value will be
   * assigned as a result of a yield expression.
   * @returns {IteratorResult<Py2JsResult, Py2JsResult>} An Object with two properties: ``done`` and ``value``.
   * When the generator yields ``some_value``, ``next`` returns ``{done :
   * false, value : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``next`` returns ``{done :
   * true, value : result_value}``.
   */
  next(arg = undefined) {
    let idresult;
    // Note: arg is optional, if arg is not supplied, it will be undefined
    // which gets converted to "Py_None". This is as intended.
    let idarg = Module.hiwire.new_value(arg);
    let done;
    try {
      idresult = Module.__pyproxyGen_Send(_getPtr(this), idarg);
      done = idresult === 0;
      if (done) {
        idresult = Module.__pyproxyGen_FetchStopIterationValue();
      }
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(idarg);
    }
    if (done && idresult === 0) {
      Module._pythonexc2js();
    }
    let value = Module.hiwire.pop_value(idresult);
    return { done, value };
  }
}

// Another layer of boilerplate. The PyProxyHandlers have some annoying logic
// to deal with straining out the spurious "Function" properties "prototype",
// "arguments", and "length", to deal with correctly satisfying the Proxy
// invariants, and to deal with the mro
function python_hasattr(jsobj, jskey) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Module.hiwire.new_value(jskey);
  let result;
  try {
    result = Module.__pyproxy_hasattr(ptrobj, idkey);
  } catch (e) {
    Module.fatal_error(e);
  } finally {
    Module.hiwire.decref(idkey);
  }
  if (result === -1) {
    Module._pythonexc2js();
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
  let cacheId = jsobj.$$.cache.cacheId;
  try {
    idresult = Module.__pyproxy_getattr(ptrobj, idkey, cacheId);
  } catch (e) {
    Module.fatal_error(e);
  } finally {
    Module.hiwire.decref(idkey);
  }
  if (idresult === 0) {
    if (Module._PyErr_Occurred()) {
      Module._pythonexc2js();
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
    errcode = Module.__pyproxy_setattr(ptrobj, idkey, idval);
  } catch (e) {
    Module.fatal_error(e);
  } finally {
    Module.hiwire.decref(idkey);
    Module.hiwire.decref(idval);
  }
  if (errcode === -1) {
    Module._pythonexc2js();
  }
}

function python_delattr(jsobj, jskey) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Module.hiwire.new_value(jskey);
  let errcode;
  try {
    errcode = Module.__pyproxy_delattr(ptrobj, idkey);
  } catch (e) {
    Module.fatal_error(e);
  } finally {
    Module.hiwire.decref(idkey);
  }
  if (errcode === -1) {
    Module._pythonexc2js();
  }
}

// See explanation of which methods should be defined here and what they do
// here:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
let PyProxyHandlers = {
  isExtensible() {
    return true;
  },
  has(jsobj, jskey) {
    // Note: must report "prototype" in proxy when we are callable.
    // (We can return the wrong value from "get" handler though.)
    let objHasKey = Reflect.has(jsobj, jskey);
    if (objHasKey) {
      return true;
    }
    // python_hasattr will crash if given a Symbol.
    if (typeof jskey === "symbol") {
      return false;
    }
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    return python_hasattr(jsobj, jskey);
  },
  get(jsobj, jskey) {
    // Preference order:
    // 1. stuff from Javascript
    // 2. the result of Python getattr

    // python_getattr will crash if given a Symbol.
    if (jskey in jsobj || typeof jskey === "symbol") {
      return Reflect.get(jsobj, jskey);
    }
    // If keys start with $ remove the $. User can use initial $ to
    // unambiguously ask for a key on the Python object.
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    // 2. The result of getattr
    let idresult = python_getattr(jsobj, jskey);
    if (idresult !== 0) {
      return Module.hiwire.pop_value(idresult);
    }
  },
  set(jsobj, jskey, jsval) {
    let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
    if (descr && !descr.writable) {
      throw new TypeError(`Cannot set read only field '${jskey}'`);
    }
    // python_setattr will crash if given a Symbol.
    if (typeof jskey === "symbol") {
      return Reflect.set(jsobj, jskey, jsval);
    }
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    python_setattr(jsobj, jskey, jsval);
    return true;
  },
  deleteProperty(jsobj, jskey) {
    let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
    if (descr && !descr.writable) {
      throw new TypeError(`Cannot delete read only field '${jskey}'`);
    }
    if (typeof jskey === "symbol") {
      return Reflect.deleteProperty(jsobj, jskey);
    }
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    python_delattr(jsobj, jskey);
    // Must return "false" if "jskey" is a nonconfigurable own property.
    // Otherwise Javascript will throw a TypeError.
    return !descr || descr.configurable;
  },
  ownKeys(jsobj) {
    let ptrobj = _getPtr(jsobj);
    let idresult;
    try {
      idresult = Module.__pyproxy_ownKeys(ptrobj);
    } catch (e) {
      Module.fatal_error(e);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    let result = Module.hiwire.pop_value(idresult);
    result.push(...Reflect.ownKeys(jsobj));
    return result;
  },
  apply(jsobj, jsthis, jsargs) {
    return jsobj.apply(jsthis, jsargs);
  },
};

/**
 * @typedef {PyProxy & Promise<Py2JsResult>} PyProxyAwaitable
 */

/**
 * The Promise / javascript awaitable API.
 * @private
 */
class PyProxyAwaitableMethods {
  /**
   * This wraps __pyproxy_ensure_future and makes a function that converts a
   * Python awaitable to a promise, scheduling the awaitable on the Python
   * event loop if necessary.
   * @private
   */
  _ensure_future() {
    let ptrobj = _getPtr(this);
    let resolveHandle;
    let rejectHandle;
    let promise = new Promise((resolve, reject) => {
      resolveHandle = resolve;
      rejectHandle = reject;
    });
    let resolve_handle_id = Module.hiwire.new_value(resolveHandle);
    let reject_handle_id = Module.hiwire.new_value(rejectHandle);
    let errcode;
    try {
      errcode = Module.__pyproxy_ensure_future(
        ptrobj,
        resolve_handle_id,
        reject_handle_id
      );
    } catch (e) {
      Module.fatal_error(e);
    } finally {
      Module.hiwire.decref(reject_handle_id);
      Module.hiwire.decref(resolve_handle_id);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
    return promise;
  }
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
   * Present only if the proxied Python object is `awaitable
   * <https://docs.python.org/3/library/asyncio-task.html?highlight=awaitable#awaitables>`_.
   *
   * @param {Function} onFulfilled A handler called with the result as an
   * argument if the awaitable succeeds.
   * @param {Function} onRejected A handler called with the error as an
   * argument if the awaitable fails.
   * @returns {Promise} The resulting Promise.
   */
  then(onFulfilled, onRejected) {
    let promise = this._ensure_future();
    return promise.then(onFulfilled, onRejected);
  }
  /**
   * Runs ``asyncio.ensure_future(awaitable)`` and executes
   * ``onRejected(error)`` if the future fails.
   *
   * See the documentation for
   * `Promise.catch
   * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/catch>`_.
   *
   * Present only if the proxied Python object is `awaitable
   * <https://docs.python.org/3/library/asyncio-task.html?highlight=awaitable#awaitables>`_.
   *
   * @param {Function} onRejected A handler called with the error as an
   * argument if the awaitable fails.
   * @returns {Promise} The resulting Promise.
   */
  catch(onRejected) {
    let promise = this._ensure_future();
    return promise.catch(onRejected);
  }
  /**
   * Runs ``asyncio.ensure_future(awaitable)`` and executes
   * ``onFinally(error)`` when the future resolves.
   *
   * See the documentation for
   * `Promise.finally
   * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/finally>`_.
   *
   * Present only if the proxied Python object is `awaitable
   * <https://docs.python.org/3/library/asyncio-task.html?highlight=awaitable#awaitables>`_.
   *
   *
   * @param {Function} onFinally A handler that is called with zero arguments
   * when the awaitable resolves.
   * @returns {Promise} A Promise that resolves or rejects with the same
   * result as the original Promise, but only after executing the
   * ``onFinally`` handler.
   */
  finally(onFinally) {
    let promise = this._ensure_future();
    return promise.finally(onFinally);
  }
}

/**
 * @typedef { PyProxy & PyProxyCallableMethods & ((...args : any[]) => Py2JsResult) } PyProxyCallable
 */
class PyProxyCallableMethods {
  apply(jsthis, jsargs) {
    return Module.callPyObject(_getPtr(this), ...jsargs);
  }
  call(jsthis, ...jsargs) {
    return Module.callPyObject(_getPtr(this), ...jsargs);
  }
  /**
   * Call the function with key word arguments.
   * The last argument must be an object with the keyword arguments.
   */
  callKwargs(...jsargs) {
    if (jsargs.length === 0) {
      throw new TypeError(
        "callKwargs requires at least one argument (the key word argument object)"
      );
    }
    let kwargs = jsargs[jsargs.length - 1];
    if (
      kwargs.constructor !== undefined &&
      kwargs.constructor.name !== "Object"
    ) {
      throw new TypeError("kwargs argument is not an object");
    }
    return Module.callPyObjectKwargs(_getPtr(this), ...jsargs);
  }
}
PyProxyCallableMethods.prototype.prototype = Function.prototype;

let type_to_array_map = new Map([
  ["i8", Int8Array],
  ["u8", Uint8Array],
  ["u8clamped", Uint8ClampedArray],
  ["i16", Int16Array],
  ["u16", Uint16Array],
  ["i32", Int32Array],
  ["u32", Uint32Array],
  ["i32", Int32Array],
  ["u32", Uint32Array],
  // if these aren't available, will be globalThis.BigInt64Array will be
  // undefined rather than raising a ReferenceError.
  ["i64", globalThis.BigInt64Array],
  ["u64", globalThis.BigUint64Array],
  ["f32", Float32Array],
  ["f64", Float64Array],
  ["dataview", DataView],
]);

/**
 * @typedef {PyProxy & PyProxyBufferMethods} PyProxyBuffer
 */
class PyProxyBufferMethods {
  /**
   * Get a view of the buffer data which is usable from Javascript. No copy is
   * ever performed.
   *
   * Present only if the proxied Python object supports the `Python Buffer
   * Protocol <https://docs.python.org/3/c-api/buffer.html>`_.
   *
   * We do not support suboffsets, if the buffer requires suboffsets we will
   * throw an error. Javascript nd array libraries can't handle suboffsets
   * anyways. In this case, you should use the :any:`toJs` api or copy the
   * buffer to one that doesn't use suboffets (using e.g.,
   * `numpy.ascontiguousarray
   * <https://numpy.org/doc/stable/reference/generated/numpy.ascontiguousarray.html>`_).
   *
   * If the buffer stores big endian data or half floats, this function will
   * fail without an explicit type argument. For big endian data you can use
   * ``toJs``. `DataViews
   * <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/DataView>`_
   * have support for big endian data, so you might want to pass
   * ``'dataview'`` as the type argument in that case.
   *
   * @param {string=} [type] The type of the :any:`PyBuffer.data <pyodide.PyBuffer.data>` field in the
   * output. Should be one of: ``"i8"``, ``"u8"``, ``"u8clamped"``, ``"i16"``,
   * ``"u16"``, ``"i32"``, ``"u32"``, ``"i32"``, ``"u32"``, ``"i64"``,
   * ``"u64"``, ``"f32"``, ``"f64``, or ``"dataview"``. This argument is
   * optional, if absent ``getBuffer`` will try to determine the appropriate
   * output type based on the buffer `format string
   * <https://docs.python.org/3/library/struct.html#format-strings>`_.
   * @returns {PyBuffer} :any:`PyBuffer <pyodide.PyBuffer>`
   */
  getBuffer(type) {
    let ArrayType = undefined;
    if (type) {
      ArrayType = type_to_array_map.get(type);
      if (ArrayType === undefined) {
        throw new Error(`Unknown type ${type}`);
      }
    }
    let HEAPU32 = Module.HEAPU32;
    let orig_stack_ptr = Module.stackSave();
    let buffer_struct_ptr = Module.stackAlloc(
      DEREF_U32(Module._buffer_struct_size, 0)
    );
    let this_ptr = _getPtr(this);
    let errcode;
    try {
      errcode = Module.__pyproxy_get_buffer(buffer_struct_ptr, this_ptr);
    } catch (e) {
      Module.fatal_error(e);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }

    // This has to match the fields in buffer_struct
    let startByteOffset = DEREF_U32(buffer_struct_ptr, 0);
    let minByteOffset = DEREF_U32(buffer_struct_ptr, 1);
    let maxByteOffset = DEREF_U32(buffer_struct_ptr, 2);

    let readonly = !!DEREF_U32(buffer_struct_ptr, 3);
    let format_ptr = DEREF_U32(buffer_struct_ptr, 4);
    let itemsize = DEREF_U32(buffer_struct_ptr, 5);
    let shape = Module.hiwire.pop_value(DEREF_U32(buffer_struct_ptr, 6));
    let strides = Module.hiwire.pop_value(DEREF_U32(buffer_struct_ptr, 7));

    let view_ptr = DEREF_U32(buffer_struct_ptr, 8);
    let c_contiguous = !!DEREF_U32(buffer_struct_ptr, 9);
    let f_contiguous = !!DEREF_U32(buffer_struct_ptr, 10);

    let format = Module.UTF8ToString(format_ptr);
    Module.stackRestore(orig_stack_ptr);

    let success = false;
    try {
      let bigEndian = false;
      if (ArrayType === undefined) {
        [ArrayType, bigEndian] = Module.processBufferFormatString(
          format,
          " In this case, you can pass an explicit type argument."
        );
      }
      let alignment = parseInt(ArrayType.name.replace(/[^0-9]/g, "")) / 8 || 1;
      if (bigEndian && alignment > 1) {
        throw new Error(
          "Javascript has no native support for big endian buffers. " +
            "In this case, you can pass an explicit type argument. " +
            "For instance, `getBuffer('dataview')` will return a `DataView`" +
            "which has native support for reading big endian data. " +
            "Alternatively, toJs will automatically convert the buffer " +
            "to little endian."
        );
      }
      let numBytes = maxByteOffset - minByteOffset;
      if (
        numBytes !== 0 &&
        (startByteOffset % alignment !== 0 ||
          minByteOffset % alignment !== 0 ||
          maxByteOffset % alignment !== 0)
      ) {
        throw new Error(
          `Buffer does not have valid alignment for a ${ArrayType.name}`
        );
      }
      let numEntries = numBytes / alignment;
      let offset = (startByteOffset - minByteOffset) / alignment;
      let data;
      if (numBytes === 0) {
        data = new ArrayType();
      } else {
        data = new ArrayType(HEAPU32.buffer, minByteOffset, numEntries);
      }
      for (let i of strides.keys()) {
        strides[i] /= alignment;
      }

      success = true;
      let result = Object.create(
        PyBuffer.prototype,
        Object.getOwnPropertyDescriptors({
          offset,
          readonly,
          format,
          itemsize,
          ndim: shape.length,
          nbytes: numBytes,
          shape,
          strides,
          data,
          c_contiguous,
          f_contiguous,
          _view_ptr: view_ptr,
          _released: false,
        })
      );
      // Module.bufferFinalizationRegistry.register(result, view_ptr, result);
      return result;
    } finally {
      if (!success) {
        try {
          Module._PyBuffer_Release(view_ptr);
          Module._PyMem_Free(view_ptr);
        } catch (e) {
          Module.fatal_error(e);
        }
      }
    }
  }
}

/**
 * @typedef {Int8Array | Uint8Array | Int16Array | Uint16Array | Int32Array | Uint32Array | Uint8ClampedArray | Float32Array | Float64Array} TypedArray;
 */

/**
 * A class to allow access to a Python data buffers from Javascript. These are
 * produced by :any:`PyProxy.getBuffer` and cannot be constructed directly.
 * When you are done, release it with the :any:`release <PyBuffer.release>`
 * method.  See
 * `Python buffer protocol documentation
 * <https://docs.python.org/3/c-api/buffer.html>`_ for more information.
 *
 * To find the element ``x[a_1, ..., a_n]``, you could use the following code:
 *
 * .. code-block:: js
 *
 *    function multiIndexToIndex(pybuff, multiIndex){
 *       if(multindex.length !==pybuff.ndim){
 *          throw new Error("Wrong length index");
 *       }
 *       let idx = pybuff.offset;
 *       for(let i = 0; i < pybuff.ndim; i++){
 *          if(multiIndex[i] < 0){
 *             multiIndex[i] = pybuff.shape[i] - multiIndex[i];
 *          }
 *          if(multiIndex[i] < 0 || multiIndex[i] >= pybuff.shape[i]){
 *             throw new Error("Index out of range");
 *          }
 *          idx += multiIndex[i] * pybuff.stride[i];
 *       }
 *       return idx;
 *    }
 *    console.log("entry is", pybuff.data[multiIndexToIndex(pybuff, [2, 0, -1])]);
 *
 * .. admonition:: Contiguity
 *    :class: warning
 *
 *    If the buffer is not contiguous, the ``data`` TypedArray will contain
 *    data that is not part of the buffer. Modifying this data may lead to
 *    undefined behavior.
 *
 * .. admonition:: Readonly buffers
 *    :class: warning
 *
 *    If ``buffer.readonly`` is ``true``, you should not modify the buffer.
 *    Modifying a readonly buffer may lead to undefined behavior.
 *
 * .. admonition:: Converting between TypedArray types
 *    :class: warning
 *
 *    The following naive code to change the type of a typed array does not
 *    work:
 *
 *    .. code-block:: js
 *
 *        // Incorrectly convert a TypedArray.
 *        // Produces a Uint16Array that points to the entire WASM memory!
 *        let myarray = new Uint16Array(buffer.data.buffer);
 *
 *    Instead, if you want to convert the output TypedArray, you need to say:
 *
 *    .. code-block:: js
 *
 *        // Correctly convert a TypedArray.
 *        let myarray = new Uint16Array(
 *            buffer.data.buffer,
 *            buffer.data.byteOffset,
 *            buffer.data.byteLength
 *        );
 */
export class PyBuffer {
  constructor() {
    /**
     * The offset of the first entry of the array. For instance if our array
     * is 3d, then you will find ``array[0,0,0]`` at
     * ``pybuf.data[pybuf.offset]``
     * @type {number}
     */
    this.offset;

    /**
     * If the data is readonly, you should not modify it. There is no way
     * for us to enforce this, but it may cause very weird behavior.
     * @type {boolean}
     */
    this.readonly;

    /**
     * The format string for the buffer. See `the Python documentation on
     * format strings
     * <https://docs.python.org/3/library/struct.html#format-strings>`_.
     * @type {string}
     */
    this.format;

    /**
     * How large is each entry (in bytes)?
     * @type {number}
     */
    this.itemsize;

    /**
     * The number of dimensions of the buffer. If ``ndim`` is 0, the buffer
     * represents a single scalar or struct. Otherwise, it represents an
     * array.
     * @type {number}
     */
    this.ndim;

    /**
     * The total number of bytes the buffer takes up. This is equal to
     * ``buff.data.byteLength``.
     * @type {number}
     */
    this.nbytes;

    /**
     * The shape of the buffer, that is how long it is in each dimension.
     * The length will be equal to ``ndim``. For instance, a 2x3x4 array
     * would have shape ``[2, 3, 4]``.
     * @type {number[]}
     */
    this.shape;

    /**
     * An array of of length ``ndim`` giving the number of elements to skip
     * to get to a new element in each dimension. See the example definition
     * of a ``multiIndexToIndex`` function above.
     * @type {number[]}
     */
    this.strides;

    /**
     * The actual data. A typed array of an appropriate size backed by a
     * segment of the WASM memory.
     *
     * The ``type`` argument of :any:`PyProxy.getBuffer`
     * determines which sort of ``TypedArray`` this is. By default
     * :any:`PyProxy.getBuffer` will look at the format string to determine the most
     * appropriate option.
     * @type {TypedArray}
     */
    this.data;

    /**
     * Is it C contiguous?
     * @type {boolean}
     */
    this.c_contiguous;

    /**
     * Is it Fortran contiguous?
     * @type {boolean}
     */
    this.f_contiguous;
    throw new TypeError("PyBuffer is not a constructor");
  }

  /**
   * Release the buffer. This allows the memory to be reclaimed.
   */
  release() {
    if (this._released) {
      return;
    }
    // Module.bufferFinalizationRegistry.unregister(this);
    try {
      Module._PyBuffer_Release(this._view_ptr);
      Module._PyMem_Free(this._view_ptr);
    } catch (e) {
      Module.fatal_error(e);
    }
    this._released = true;
    this.data = null;
  }
}

// A special proxy that we use to wrap pyodide.globals to allow property
// access like `pyodide.globals.x`.
let globalsPropertyAccessWarned = false;
let globalsPropertyAccessWarningMsg =
  "Access to pyodide.globals via pyodide.globals.key is deprecated and " +
  "will be removed in version 0.18.0. Use pyodide.globals.get('key'), " +
  "pyodide.globals.set('key', value), pyodide.globals.delete('key') instead.";
let NamespaceProxyHandlers = {
  has(obj, key) {
    return Reflect.has(obj, key) || obj.has(key);
  },
  get(obj, key) {
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
  set(obj, key, value) {
    if (Reflect.has(obj, key)) {
      throw new Error(`Cannot set read only field ${key}`);
    }
    if (!globalsPropertyAccessWarned) {
      globalsPropertyAccessWarned = true;
      console.warn(globalsPropertyAccessWarningMsg);
    }
    obj.set(key, value);
  },
  ownKeys(obj) {
    let result = new Set(Reflect.ownKeys(obj));
    let iter = obj.keys();
    for (let key of iter) {
      result.add(key);
    }
    iter.destroy();
    return Array.from(result);
  },
};

export function wrapNamespace(ns) {
  return new Proxy(ns, NamespaceProxyHandlers);
}
