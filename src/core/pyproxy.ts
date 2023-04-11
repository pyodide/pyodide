/**
 * Every public Python entrypoint goes through this file! The main entrypoint is
 * the callPyObject method, but of course one can also execute arbitrary code
 * via the various __dundermethods__ associated to classes.
 *
 * Any time we call into wasm, the call should be wrapped in a try catch block.
 * This way if a JavaScript error emerges from the wasm, we can escalate it to a
 * fatal error.
 *
 * This is file is preprocessed with -imacros "pyproxy.c". As a result of this,
 * any macros available in pyproxy.c are available here. We only need the flags
 * macros HAS_LENGTH, etc.
 *
 * See Makefile recipe for src/js/pyproxy.gen.ts
 */

declare var Module: any;
declare var Hiwire: any;
declare var API: any;
declare var HEAPU32: Uint32Array;

declare function _check_gil(): void;
declare function stackSave(): number;
declare function stackRestore(ptr: number): void;
declare function stackAlloc(size: number): number;

import { warnOnce } from "./util";

// pyodide-skip

// Just for this file, we implement a special "skip" pragma. These lines are
// skipped by the Makefile when producing pyproxy.gen.ts These are actually C
// macros, but we declare them to make typescript okay with processing the raw
// file. We need to process the raw file to generate the docs because the C
// preprocessor deletes comments which kills all the docstrings.

// These declarations make Typescript accept the raw file. However, if we macro
// preprocess these lines, we get a bunch of syntax errors so they need to be
// removed from the preprocessed version.

// This also has the benefit that it makes intellisense happy.
declare var IS_CALLABLE: number;
declare var HAS_LENGTH: number;
declare var HAS_GET: number;
declare var HAS_SET: number;
declare var HAS_CONTAINS: number;
declare var IS_ITERABLE: number;
declare var IS_ITERATOR: number;
declare var IS_AWAITABLE: number;
declare var IS_BUFFER: number;
declare var IS_ASYNC_ITERABLE: number;
declare var IS_ASYNC_ITERATOR: number;
declare var IS_GENERATOR: number;
declare var IS_ASYNC_GENERATOR: number;

declare var PYGEN_NEXT: number;
declare var PYGEN_RETURN: number;
declare var PYGEN_ERROR: number;

declare function DEREF_U32(ptr: number, offset: number): number;
declare function Py_ENTER(): void;
declare function Py_EXIT(): void;
// end-pyodide-skip

function isPyProxy(jsobj: any): jsobj is PyProxy {
  return jsobj instanceof PyProxy;
}
API.isPyProxy = isPyProxy;

declare var FinalizationRegistry: any;
declare var globalThis: any;

if (globalThis.FinalizationRegistry) {
  Module.finalizationRegistry = new FinalizationRegistry(
    ([ptr, cache]: [ptr: number, cache: PyProxyCache]) => {
      if (cache) {
        cache.leaked = true;
        pyproxy_decref_cache(cache);
      }
      try {
        Py_ENTER();
        Module._Py_DecRef(ptr);
        Py_EXIT();
      } catch (e) {
        // I'm not really sure what happens if an error occurs inside of a
        // finalizer...
        API.fatal_error(e);
      }
    },
  );
  // For some unclear reason this code screws up selenium FirefoxDriver. Works
  // fine in chrome and when I test it in browser. It seems to be sensitive to
  // changes that don't make a difference to the semantics.
  // TODO: after 0.18.0, fix selenium issues with this code.
  // Module.bufferFinalizationRegistry = new FinalizationRegistry((ptr) => {
  //   try {
  //     Module._PyBuffer_Release(ptr);
  //     Module._PyMem_Free(ptr);
  //   } catch (e) {
  //     API.fatal_error(e);
  //   }
  // });
} else {
  Module.finalizationRegistry = { register() {}, unregister() {} };
  // Module.bufferFinalizationRegistry = finalizationRegistry;
}

let pyproxy_alloc_map = new Map();
Module.pyproxy_alloc_map = pyproxy_alloc_map;
let trace_pyproxy_alloc: (proxy: any) => void;
let trace_pyproxy_dealloc: (proxy: any) => void;

Module.enable_pyproxy_allocation_tracing = function () {
  trace_pyproxy_alloc = function (proxy: any) {
    pyproxy_alloc_map.set(proxy, Error().stack);
  };
  trace_pyproxy_dealloc = function (proxy: any) {
    pyproxy_alloc_map.delete(proxy);
  };
};
Module.disable_pyproxy_allocation_tracing = function () {
  trace_pyproxy_alloc = function (proxy: any) {};
  trace_pyproxy_dealloc = function (proxy: any) {};
};
Module.disable_pyproxy_allocation_tracing();

type PyProxyCache = { cacheId: number; refcnt: number; leaked?: boolean };
type PyProxyProps = {
  /**
   * captureThis tracks whether this should be passed as the first argument to
   * the Python function or not. We keep it false by default. To make a PyProxy
   * where the ``this`` argument is included, call the :js:meth:`captureThis` method.
   */
  captureThis: boolean;
  /**
   * isBound tracks whether bind has been called
   */
  isBound: boolean;
  /**
   * the ``this`` value that has been bound to the PyProxy
   */
  boundThis?: any;
  /**
   * Any extra arguments passed to bind are used for partial function
   * application. These are stored here.
   */
  boundArgs: any[];
  roundtrip: boolean;
};

/**
 * Create a new PyProxy wrapping ptrobj which is a PyObject*.
 *
 * The argument cache is only needed to implement the PyProxy.copy API, it
 * allows the copy of the PyProxy to share its attribute cache with the original
 * version. In all other cases, pyproxy_new should be called with one argument.
 *
 * In the case that the Python object is callable, PyProxy inherits from
 * Function so that PyProxy objects can be callable. In that case we MUST expose
 * certain properties inherited from Function, but we do our best to remove as
 * many as possible.
 * @private
 */
function pyproxy_new(
  ptrobj: number,
  {
    flags: flags_arg,
    cache,
    props,
    $$,
  }: {
    flags?: number;
    cache?: PyProxyCache;
    $$?: any;
    roundtrip?: boolean;
    props?: any;
  } = {},
): PyProxy {
  const flags =
    flags_arg !== undefined ? flags_arg : Module._pyproxy_getflags(ptrobj);
  if (flags === -1) {
    Module._pythonexc2js();
  }
  const cls = Module.getPyProxyClass(flags);
  let target;
  if (flags & IS_CALLABLE) {
    // In this case we are effectively subclassing Function in order to ensure
    // that the proxy is callable. With a Content Security Protocol that doesn't
    // allow unsafe-eval, we can't invoke the Function constructor directly. So
    // instead we create a function in the universally allowed way and then use
    // `setPrototypeOf`. The documentation for `setPrototypeOf` says to use
    // `Object.create` or `Reflect.construct` instead for performance reasons
    // but neither of those work here.
    target = function () {};
    Object.setPrototypeOf(target, cls.prototype);
    // Remove undesirable properties added by Function constructor. Note: we
    // can't remove "arguments" or "caller" because they are not configurable
    // and not writable
    // @ts-ignore
    delete target.length;
    // @ts-ignore
    delete target.name;
    // prototype isn't configurable so we can't delete it but it's writable.
    target.prototype = undefined;
  } else {
    target = Object.create(cls.prototype);
  }

  const isAlias = !!$$;

  if (!isAlias) {
    if (!cache) {
      // The cache needs to be accessed primarily from the C function
      // _pyproxy_getattr so we make a hiwire id.
      let cacheId = Hiwire.new_value(new Map());
      cache = { cacheId, refcnt: 0 };
    }
    cache.refcnt++;
    $$ = { ptr: ptrobj, type: "PyProxy", cache, flags };
    Module.finalizationRegistry.register($$, [ptrobj, cache], $$);
    Module._Py_IncRef(ptrobj);
  }

  Object.defineProperty(target, "$$", { value: $$ });
  if (!props) {
    props = {};
  }
  props = Object.assign(
    { isBound: false, captureThis: false, boundArgs: [], roundtrip: false },
    props,
  );
  Object.defineProperty(target, "$$props", { value: props });

  let proxy = new Proxy(target, PyProxyHandlers);
  if (!isAlias) {
    trace_pyproxy_alloc(proxy);
  }
  return proxy;
}
Module.pyproxy_new = pyproxy_new;

function _getPtr(jsobj: any) {
  let ptr: number = jsobj.$$.ptr;
  if (ptr === 0) {
    throw new Error(jsobj.$$.destroyed_msg);
  }
  return ptr;
}

function _adjustArgs(proxyobj: any, jsthis: any, jsargs: any[]): any[] {
  const { captureThis, boundArgs, boundThis, isBound } =
    proxyobj.$$props as PyProxyProps;
  if (captureThis) {
    if (isBound) {
      return [boundThis].concat(boundArgs, jsargs);
    } else {
      return [jsthis].concat(jsargs);
    }
  }
  if (isBound) {
    return boundArgs.concat(jsargs);
  }
  return jsargs;
}

let pyproxyClassMap = new Map();
/**
 * Retrieve the appropriate mixins based on the features requested in flags.
 * Used by pyproxy_new. The "flags" variable is produced by the C function
 * pyproxy_getflags. Multiple PyProxies with the same set of feature flags
 * will share the same prototype, so the memory footprint of each individual
 * PyProxy is minimal.
 * @private
 */
Module.getPyProxyClass = function (flags: number) {
  const FLAG_TYPE_PAIRS: [number, any][] = [
    [HAS_LENGTH, PyLengthMethods],
    [HAS_GET, PyGetItemMethods],
    [HAS_SET, PySetItemMethods],
    [HAS_CONTAINS, PyContainsMethods],
    [IS_ITERABLE, PyIterableMethods],
    [IS_ITERATOR, PyIteratorMethods],
    [IS_GENERATOR, PyGeneratorMethods],
    [IS_ASYNC_ITERABLE, PyAsyncIterableMethods],
    [IS_ASYNC_ITERATOR, PyAsyncIteratorMethods],
    [IS_ASYNC_GENERATOR, PyAsyncGeneratorMethods],
    [IS_AWAITABLE, PyAwaitableMethods],
    [IS_BUFFER, PyBufferMethods],
    [IS_CALLABLE, PyCallableMethods],
  ];
  let result = pyproxyClassMap.get(flags);
  if (result) {
    return result;
  }
  let descriptors: any = {};
  for (let [feature_flag, methods] of FLAG_TYPE_PAIRS) {
    if (flags & feature_flag) {
      Object.assign(
        descriptors,
        Object.getOwnPropertyDescriptors(methods.prototype),
      );
    }
  }
  // Use base constructor (just throws an error if construction is attempted).
  descriptors.constructor = Object.getOwnPropertyDescriptor(
    PyProxy.prototype,
    "constructor",
  );
  Object.assign(
    descriptors,
    Object.getOwnPropertyDescriptors({ $$flags: flags }),
  );
  let new_proto = Object.create(PyProxy.prototype, descriptors);
  function NewPyProxyClass() {}
  NewPyProxyClass.prototype = new_proto;
  pyproxyClassMap.set(flags, NewPyProxyClass);
  return NewPyProxyClass;
};

// Static methods
Module.PyProxy_getPtr = _getPtr;

const pyproxy_cache_destroyed_msg =
  "This borrowed attribute proxy was automatically destroyed in the " +
  "process of destroying the proxy it was borrowed from. Try using the 'copy' method.";

function pyproxy_decref_cache(cache: PyProxyCache) {
  if (!cache) {
    return;
  }
  cache.refcnt--;
  if (cache.refcnt === 0) {
    let cache_map = Hiwire.pop_value(cache.cacheId);
    for (let proxy_id of cache_map.values()) {
      const cache_entry = Hiwire.pop_value(proxy_id);
      if (!cache.leaked) {
        Module.pyproxy_destroy(cache_entry, pyproxy_cache_destroyed_msg, true);
      }
    }
  }
}

Module.pyproxy_destroy = function (
  proxy: PyProxy,
  destroyed_msg: string,
  destroy_roundtrip: boolean,
) {
  if (proxy.$$.ptr === 0) {
    return;
  }
  if (!destroy_roundtrip && proxy.$$props.roundtrip) {
    return;
  }
  let ptrobj = _getPtr(proxy);
  Module.finalizationRegistry.unregister(proxy.$$);
  destroyed_msg = destroyed_msg || "Object has already been destroyed";
  let proxy_type = proxy.type;
  let proxy_repr;
  try {
    proxy_repr = proxy.toString();
  } catch (e) {
    if ((e as any).pyodide_fatal_error) {
      throw e;
    }
  }
  // Maybe the destructor will call JavaScript code that will somehow try
  // to use this proxy. Mark it deleted before decrementing reference count
  // just in case!
  proxy.$$.ptr = 0;
  destroyed_msg += "\n" + `The object was of type "${proxy_type}" and `;
  if (proxy_repr) {
    destroyed_msg += `had repr "${proxy_repr}"`;
  } else {
    destroyed_msg += "an error was raised when trying to generate its repr";
  }
  proxy.$$.destroyed_msg = destroyed_msg;
  pyproxy_decref_cache(proxy.$$.cache);
  try {
    Py_ENTER();
    Module._Py_DecRef(ptrobj);
    trace_pyproxy_dealloc(proxy);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
};

// Now a lot of boilerplate to wrap the abstract Object protocol wrappers
// defined in pyproxy.c in JavaScript functions.

Module.callPyObjectKwargs = function (
  ptrobj: number,
  jsargs: any,
  kwargs: any,
) {
  // We don't do any checking for kwargs, checks are in PyProxy.callKwargs
  // which only is used when the keyword arguments come from the user.
  let num_pos_args = jsargs.length;
  let kwargs_names = Object.keys(kwargs);
  let kwargs_values = Object.values(kwargs);
  let num_kwargs = kwargs_names.length;
  jsargs.push(...kwargs_values);

  let idargs = Hiwire.new_value(jsargs);
  let idkwnames = Hiwire.new_value(kwargs_names);
  let idresult;
  try {
    Py_ENTER();
    idresult = Module.__pyproxy_apply(
      ptrobj,
      idargs,
      num_pos_args,
      idkwnames,
      num_kwargs,
    );
    Py_EXIT();
  } catch (e) {
    if (API._skip_unwind_fatal_error) {
      API.maybe_fatal_error(e);
    } else {
      API.fatal_error(e);
    }
    return;
  } finally {
    Hiwire.decref(idargs);
    Hiwire.decref(idkwnames);
  }
  if (idresult === 0) {
    Module._pythonexc2js();
  }
  let result = Hiwire.pop_value(idresult);
  // Automatically schedule coroutines
  if (result && result.type === "coroutine" && result._ensure_future) {
    result._ensure_future();
  }
  return result;
};

Module.callPyObject = function (ptrobj: number, jsargs: any) {
  return Module.callPyObjectKwargs(ptrobj, jsargs, {});
};

export interface PyProxy {
  [x: string]: any;
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` is an object that allows idiomatic use of a Python object from
 * JavaScript. See :ref:`type-translations-pyproxy`.
 */
export class PyProxy {
  /** @private */
  $$: {
    ptr: number;
    cache: PyProxyCache;
    destroyed_msg?: string;
  };
  /** @private */
  $$props: PyProxyProps;
  /** @private */
  $$flags: number;

  /**
   * @private
   * @hideconstructor
   */
  constructor() {
    throw new TypeError("PyProxy is not a constructor");
  }

  /** @private */
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
   */
  get type(): string {
    let ptrobj = _getPtr(this);
    return Hiwire.pop_value(Module.__pyproxy_type(ptrobj));
  }
  toString(): string {
    let ptrobj = _getPtr(this);
    let jsref_repr;
    try {
      Py_ENTER();
      jsref_repr = Module.__pyproxy_repr(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (jsref_repr === 0) {
      Module._pythonexc2js();
    }
    return Hiwire.pop_value(jsref_repr);
  }
  /**
   * Destroy the :js:class:`~pyodide.ffi.PyProxy`. This will release the memory. Any further attempt
   * to use the object will raise an error.
   *
   * In a browser supporting :js:data:`FinalizationRegistry`, Pyodide will
   * automatically destroy the :js:class:`~pyodide.ffi.PyProxy` when it is garbage collected, however
   * there is no guarantee that the finalizer will be run in a timely manner so
   * it is better to destroy the proxy explicitly.
   *
   * @param options
   * @param options.message The error message to print if use is attempted after
   *        destroying. Defaults to "Object has already been destroyed".
   *
   */
  destroy(options: { message?: string; destroyRoundtrip?: boolean } = {}) {
    options = Object.assign({ message: "", destroyRoundtrip: true }, options);
    const { message: m, destroyRoundtrip: d } = options;
    Module.pyproxy_destroy(this, m, d);
  }
  /**
   * Make a new :js:class:`~pyodide.ffi.PyProxy` pointing to the same Python object.
   * Useful if the :js:class:`~pyodide.ffi.PyProxy` is destroyed somewhere else.
   */
  copy(): PyProxy {
    let ptrobj = _getPtr(this);
    return pyproxy_new(ptrobj, {
      flags: this.$$flags,
      cache: this.$$.cache,
      props: this.$$props,
    });
  }
  /**
   * Converts the :js:class:`~pyodide.ffi.PyProxy` into a JavaScript object as best as possible. By
   * default does a deep conversion, if a shallow conversion is desired, you can
   * use ``proxy.toJs({depth : 1})``. See :ref:`Explicit Conversion of PyProxy
   * <type-translations-pyproxy-to-js>` for more info.
   * @param options
   * @return The JavaScript object resulting from the conversion.
   */
  toJs({
    depth = -1,
    pyproxies = undefined,
    create_pyproxies = true,
    dict_converter = undefined,
    default_converter = undefined,
  }: {
    /** How many layers deep to perform the conversion. Defaults to infinite */
    depth?: number;
    /**
     * If provided, :js:meth:`toJs` will store all PyProxies created in this
     * list. This allows you to easily destroy all the PyProxies by iterating
     * the list without having to recurse over the generated structure. The most
     * common use case is to create a new empty list, pass the list as
     * ``pyproxies``, and then later iterate over ``pyproxies`` to destroy all of
     * created proxies.
     */
    pyproxies?: PyProxy[];
    /**
     * If false, :js:meth:`toJs` will throw a
     * :py:exc:`~pyodide.ffi.ConversionError` rather than producing a
     * :js:class:`~pyodide.ffi.PyProxy`.
     */
    create_pyproxies?: boolean;
    /**
     * A function to be called on an iterable of pairs ``[key, value]``. Convert
     * this iterable of pairs to the desired output. For instance,
     * :js:func:`Object.fromEntries` would convert the dict to an object,
     * :js:func:`Array.from` converts it to an :js:class:`Array` of pairs, and
     * ``(it) => new Map(it)`` converts it to a :js:class:`Map` (which is the
     * default behavior).
     */
    dict_converter?: (array: Iterable<[key: string, value: any]>) => any;
    /**
     * Optional argument to convert objects with no default conversion. See the
     * documentation of :meth:`~pyodide.ffi.to_js`.
     */
    default_converter?: (
      obj: PyProxy,
      convert: (obj: PyProxy) => any,
      cacheConversion: (obj: PyProxy, result: any) => void,
    ) => any;
  } = {}): any {
    let ptrobj = _getPtr(this);
    let idresult;
    let proxies_id;
    let dict_converter_id = 0;
    let default_converter_id = 0;
    if (!create_pyproxies) {
      proxies_id = 0;
    } else if (pyproxies) {
      proxies_id = Hiwire.new_value(pyproxies);
    } else {
      proxies_id = Hiwire.new_value([]);
    }
    if (dict_converter) {
      dict_converter_id = Hiwire.new_value(dict_converter);
    }
    if (default_converter) {
      default_converter_id = Hiwire.new_value(default_converter);
    }
    try {
      Py_ENTER();
      idresult = Module._python2js_custom(
        ptrobj,
        depth,
        proxies_id,
        dict_converter_id,
        default_converter_id,
      );
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(proxies_id);
      Hiwire.decref(dict_converter_id);
      Hiwire.decref(default_converter_id);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    return Hiwire.pop_value(idresult);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyProxyWithLength`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyProxyWithLength`` instead.
   */
  @warnOnce(
    "supportsLength() is deprecated. Use `instanceof pyodide.ffi.PyProxyWithLength` instead.",
  )
  supportsLength(): this is PyProxyWithLength {
    return !!(this.$$flags & HAS_LENGTH);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyProxyWithGet`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyProxyWithGet`` instead.
   */
  @warnOnce(
    "supportsGet() is deprecated. Use `instanceof pyodide.ffi.PyProxyWithGet` instead.",
  )
  supportsGet(): this is PyProxyWithGet {
    return !!(this.$$flags & HAS_GET);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyProxyWithSet`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyProxyWithSet`` instead.
   */
  @warnOnce(
    "supportsSet() is deprecated. Use `instanceof pyodide.ffi.PyProxyWithSet` instead.",
  )
  supportsSet(): this is PyProxyWithSet {
    return !!(this.$$flags & HAS_SET);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyProxyWithHas`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyProxyWithHas`` instead.
   */
  @warnOnce(
    "supportsHas() is deprecated. Use `instanceof pyodide.ffi.PyProxyWithHas` instead.",
  )
  supportsHas(): this is PyProxyWithHas {
    return !!(this.$$flags & HAS_CONTAINS);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a
   * :js:class:`~pyodide.ffi.PyIterable`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyIterable`` instead.
   */
  @warnOnce(
    "isIterable() is deprecated. Use `instanceof pyodide.ffi.PyIterable` instead.",
  )
  isIterable(): this is PyIterable {
    return !!(this.$$flags & (IS_ITERABLE | IS_ITERATOR));
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a
   * :js:class:`~pyodide.ffi.PyIterator`
   * @deprecated Use ``obj instanceof pyodide.ffi.PyIterator`` instead.
   */
  @warnOnce(
    "isIterator() is deprecated. Use `instanceof pyodide.ffi.PyIterator` instead.",
  )
  isIterator(): this is PyIterator {
    return !!(this.$$flags & IS_ITERATOR);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyAwaitable`
   * @deprecated Use :js:class:`obj instanceof pyodide.ffi.PyAwaitable <pyodide.ffi.PyAwaitable>` instead.
   */
  @warnOnce(
    "isAwaitable() is deprecated. Use `instanceof pyodide.ffi.PyAwaitable` instead.",
  )
  isAwaitable(): this is PyAwaitable {
    return !!(this.$$flags & IS_AWAITABLE);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyBuffer`.
   * @deprecated Use ``obj instanceof pyodide.ffi.PyBuffer`` instead.
   */
  @warnOnce(
    "isBuffer() is deprecated. Use `instanceof pyodide.ffi.PyBuffer` instead.",
  )
  isBuffer(): this is PyBuffer {
    return !!(this.$$flags & IS_BUFFER);
  }
  /**
   * Check whether the :js:class:`~pyodide.ffi.PyProxy` is a :js:class:`~pyodide.ffi.PyCallable`.
   * @deprecated ``obj instanceof pyodide.ffi.PyCallable`` instead.
   */
  @warnOnce(
    "isCallable() is deprecated. Use `instanceof pyodide.ffi.PyCallable` instead.",
  )
  isCallable(): this is PyCallable {
    return !!(this.$$flags & IS_CALLABLE);
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a :meth:`~object.__len__`
 * method.
 */
export class PyProxyWithLength extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & HAS_LENGTH);
  }
}

export interface PyProxyWithLength extends PyLengthMethods {}

// Controlled by HAS_LENGTH, appears for any object with __len__ or sq_length
// or mp_length methods
export class PyLengthMethods {
  /**
   * The length of the object.
   */
  get length(): number {
    let ptrobj = _getPtr(this);
    let length;
    try {
      Py_ENTER();
      length = Module._PyObject_Size(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (length === -1) {
      Module._pythonexc2js();
    }
    return length;
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a
 * :meth:`~object.__getitem__` method.
 */
export class PyProxyWithGet extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & HAS_GET);
  }
}

export interface PyProxyWithGet extends PyGetItemMethods {}

// Controlled by HAS_GET, appears for any class with __getitem__,
// mp_subscript, or sq_item methods
export class PyGetItemMethods {
  /**
   * This translates to the Python code ``obj[key]``.
   *
   * @param key The key to look up.
   * @returns The corresponding value.
   */
  get(key: any): any {
    let ptrobj = _getPtr(this);
    let idkey = Hiwire.new_value(key);
    let idresult;
    try {
      Py_ENTER();
      idresult = Module.__pyproxy_getitem(ptrobj, idkey);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idkey);
    }
    if (idresult === 0) {
      if (Module._PyErr_Occurred()) {
        Module._pythonexc2js();
      } else {
        return undefined;
      }
    }
    return Hiwire.pop_value(idresult);
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a
 * :meth:`~object.__setitem__` or :meth:`~object.__delitem__` method.
 */
export class PyProxyWithSet extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & HAS_SET);
  }
}

export interface PyProxyWithSet extends PySetItemMethods {}
// Controlled by HAS_SET, appears for any class with __setitem__, __delitem__,
// mp_ass_subscript,  or sq_ass_item.
export class PySetItemMethods {
  /**
   * This translates to the Python code ``obj[key] = value``.
   *
   * @param key The key to set.
   * @param value The value to set it to.
   */
  set(key: any, value: any) {
    let ptrobj = _getPtr(this);
    let idkey = Hiwire.new_value(key);
    let idval = Hiwire.new_value(value);
    let errcode;
    try {
      Py_ENTER();
      errcode = Module.__pyproxy_setitem(ptrobj, idkey, idval);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idkey);
      Hiwire.decref(idval);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
  }
  /**
   * This translates to the Python code ``del obj[key]``.
   *
   * @param key The key to delete.
   */
  delete(key: any) {
    let ptrobj = _getPtr(this);
    let idkey = Hiwire.new_value(key);
    let errcode;
    try {
      Py_ENTER();
      errcode = Module.__pyproxy_delitem(ptrobj, idkey);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idkey);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a
 * :meth:`~object.__contains__` method.
 */
export class PyProxyWithHas extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & HAS_CONTAINS);
  }
}

export interface PyProxyWithHas extends PyContainsMethods {}

// Controlled by HAS_CONTAINS flag, appears for any class with __contains__ or
// sq_contains
export class PyContainsMethods {
  /**
   * This translates to the Python code ``key in obj``.
   *
   * @param key The key to check for.
   * @returns Is ``key`` present?
   */
  has(key: any): boolean {
    let ptrobj = _getPtr(this);
    let idkey = Hiwire.new_value(key);
    let result;
    try {
      Py_ENTER();
      result = Module.__pyproxy_contains(ptrobj, idkey);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idkey);
    }
    if (result === -1) {
      Module._pythonexc2js();
    }
    return result === 1;
  }
}

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
function* iter_helper(iterptr: number, token: {}): Generator<any> {
  try {
    while (true) {
      Py_ENTER();
      const item = Module.__pyproxy_iter_next(iterptr);
      if (item === 0) {
        break;
      }
      Py_EXIT();
      yield Hiwire.pop_value(item);
    }
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Module.finalizationRegistry.unregister(token);
    Module._Py_DecRef(iterptr);
  }
  if (Module._PyErr_Occurred()) {
    Module._pythonexc2js();
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is :std:term:`iterable`
 * (i.e., it has an :meth:`~object.__iter__` method).
 */
export class PyIterable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & (IS_ITERABLE | IS_ITERATOR));
  }
}

export interface PyIterable extends PyIterableMethods {}

/** @deprecated Use :js:class:`pyodide.ffi.PyIterable` instead. */
export type PyProxyIterable = PyIterable;

// Controlled by IS_ITERABLE, appears for any object with __iter__ or tp_iter,
// unless they are iterators. See: https://docs.python.org/3/c-api/iter.html
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols
// This avoids allocating a PyProxy wrapper for the temporary iterator.
export class PyIterableMethods {
  /**
   * This translates to the Python code ``iter(obj)``. Return an iterator
   * associated to the proxy. See the documentation for
   * :js:data:`Symbol.iterator`.
   *
   * This will be used implicitly by ``for(let x of proxy){}``.
   */
  [Symbol.iterator](): Iterator<any, any, any> {
    let ptrobj = _getPtr(this);
    let token = {};
    let iterptr;
    try {
      Py_ENTER();
      iterptr = Module._PyObject_GetIter(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (iterptr === 0) {
      Module._pythonexc2js();
    }

    let result = iter_helper(iterptr, token);
    Module.finalizationRegistry.register(result, [iterptr, undefined], token);
    return result;
  }
}

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
async function* aiter_helper(iterptr: number, token: {}): AsyncGenerator<any> {
  try {
    while (true) {
      let item, p;
      try {
        Py_ENTER();
        item = Module.__pyproxy_aiter_next(iterptr);
        Py_EXIT();
        if (item === 0) {
          break;
        }
        p = Hiwire.pop_value(item);
      } catch (e) {
        API.fatal_error(e);
      }
      try {
        yield await p;
      } catch (e) {
        if (
          e &&
          typeof e === "object" &&
          (e as any).type === "StopAsyncIteration"
        ) {
          return;
        }
        throw e;
      } finally {
        p.destroy();
      }
    }
  } finally {
    Module.finalizationRegistry.unregister(token);
    Module._Py_DecRef(iterptr);
  }
  if (Module._PyErr_Occurred()) {
    Module._pythonexc2js();
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is :std:term:`asynchronous
 * iterable` (i.e., has an :meth:`~object.__aiter__` method).
 */
export class PyAsyncIterable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return (
      API.isPyProxy(obj) &&
      !!(obj.$$flags & (IS_ASYNC_ITERABLE | IS_ASYNC_ITERATOR))
    );
  }
}

export interface PyAsyncIterable extends PyAsyncIterableMethods {}

export class PyAsyncIterableMethods {
  /**
   * This translates to the Python code ``aiter(obj)``. Return an async iterator
   * associated to the proxy. See the documentation for :js:data:`Symbol.asyncIterator`.
   *
   * This will be used implicitly by ``for(await let x of proxy){}``.
   */
  [Symbol.asyncIterator](): AsyncIterator<any, any, any> {
    let ptrobj = _getPtr(this);
    let token = {};
    let iterptr;
    try {
      Py_ENTER();
      iterptr = Module._PyObject_GetAIter(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (iterptr === 0) {
      Module._pythonexc2js();
    }

    let result = aiter_helper(iterptr, token);
    Module.finalizationRegistry.register(result, [iterptr, undefined], token);
    return result;
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an :term:`iterator`
 * (i.e., has a :meth:`~generator.send` or :meth:`~iterator.__next__` method).
 */
export class PyIterator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_ITERATOR);
  }
}

export interface PyIterator extends PyIteratorMethods {}

/** @deprecated Use :js:class:`pyodide.ffi.PyIterator` instead. */
export type PyProxyIterator = PyIterator;

// Controlled by IS_ITERATOR, appears for any object with a __next__ or
// tp_iternext method.
export class PyIteratorMethods {
  /** @private */
  [Symbol.iterator]() {
    return this;
  }
  /**
   * This translates to the Python code ``next(obj)``. Returns the next value of
   * the generator. See the documentation for :js:meth:`Generator.next` The
   * argument will be sent to the Python generator.
   *
   * This will be used implicitly by ``for(let x of proxy){}``.
   *
   * @param any The value to send to the generator. The value will be assigned
   * as a result of a yield expression.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``next`` returns ``{done : false, value :
   * some_value}``. When the generator raises a :py:exc:`StopIteration`
   * exception, ``next`` returns ``{done : true, value : result_value}``.
   */
  next(arg: any = undefined): IteratorResult<any, any> {
    // Note: arg is optional, if arg is not supplied, it will be undefined
    // which gets converted to "Py_None". This is as intended.
    let idarg = Hiwire.new_value(arg);
    let status;
    let done;
    let stackTop = stackSave();
    let res_ptr = stackAlloc(4);
    try {
      Py_ENTER();
      status = Module.__pyproxyGen_Send(_getPtr(this), idarg, res_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idarg);
    }
    let idresult = DEREF_U32(res_ptr, 0);
    stackRestore(stackTop);
    if (status === PYGEN_ERROR) {
      Module._pythonexc2js();
    }
    let value = Hiwire.pop_value(idresult);
    done = status === PYGEN_RETURN;
    return { done, value };
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is a :std:term:`generator`
 * (i.e., it is an instance of :py:class:`~collections.abc.Generator`).
 */
export class PyGenerator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_GENERATOR);
  }
}

export interface PyGenerator extends PyGeneratorMethods {}

export class PyGeneratorMethods {
  /**
   * Throws an exception into the Generator.
   *
   * See the documentation for :js:meth:`Generator.throw`.
   *
   * @param exception Error The error to throw into the generator. Must be an
   * instanceof ``Error``.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  throw(exc: any): IteratorResult<any, any> {
    let idarg = Hiwire.new_value(exc);
    let status;
    let done;
    let stackTop = stackSave();
    let res_ptr = stackAlloc(4);
    try {
      Py_ENTER();
      status = Module.__pyproxyGen_throw(_getPtr(this), idarg, res_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idarg);
    }
    let idresult = DEREF_U32(res_ptr, 0);
    stackRestore(stackTop);
    if (status === PYGEN_ERROR) {
      Module._pythonexc2js();
    }
    let value = Hiwire.pop_value(idresult);
    done = status === PYGEN_RETURN;
    return { done, value };
  }

  /**
   * Throws a :py:exc:`GeneratorExit` into the generator and if the
   * :py:exc:`GeneratorExit` is not caught returns the argument value ``{done:
   * true, value: v}``. If the generator catches the :py:exc:`GeneratorExit` and
   * returns or yields another value the next value of the generator this is
   * returned in the normal way. If it throws some error other than
   * :py:exc:`GeneratorExit` or :py:exc:`StopIteration`, that error is propagated. See
   * the documentation for :js:meth:`Generator.return`.
   *
   * @param any The value to return from the generator.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  return(v: any): IteratorResult<any, any> {
    // Note: arg is optional, if arg is not supplied, it will be undefined
    // which gets converted to "Py_None". This is as intended.
    let idarg = Hiwire.new_value(v);
    let status;
    let done;
    let stackTop = stackSave();
    let res_ptr = stackAlloc(4);
    try {
      Py_ENTER();
      status = Module.__pyproxyGen_return(_getPtr(this), idarg, res_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idarg);
    }
    let idresult = DEREF_U32(res_ptr, 0);
    stackRestore(stackTop);
    if (status === PYGEN_ERROR) {
      Module._pythonexc2js();
    }
    let value = Hiwire.pop_value(idresult);
    done = status === PYGEN_RETURN;
    return { done, value };
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an
 * :std:term:`asynchronous iterator`
 */
export class PyAsyncIterator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_ASYNC_ITERATOR);
  }
}

export interface PyAsyncIterator extends PyAsyncIteratorMethods {}

export class PyAsyncIteratorMethods {
  /** @private */
  [Symbol.asyncIterator]() {
    return this;
  }
  /**
   * This translates to the Python code ``anext(obj)``. Returns the next value
   * of the asynchronous iterator. The argument will be sent to the Python
   * iterator (if it's a generator for instance).
   *
   * This will be used implicitly by ``for(let x of proxy){}``.
   *
   * @param any The value to send to a generator. The value will be assigned as
   * a result of a yield expression.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * iterator yields ``some_value``, ``next`` returns ``{done : false, value :
   * some_value}``. When the giterator is done, ``next`` returns
   * ``{done : true }``.
   */
  async next(arg: any = undefined): Promise<IteratorResult<any, any>> {
    let idarg = Hiwire.new_value(arg);
    let idresult;
    try {
      Py_ENTER();
      idresult = Module.__pyproxyGen_asend(_getPtr(this), idarg);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idarg);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    const p = Hiwire.pop_value(idresult);
    let value;
    try {
      value = await p;
    } catch (e) {
      if (
        e &&
        typeof e === "object" &&
        (e as any).type === "StopAsyncIteration"
      ) {
        return { done: true, value };
      }
      throw e;
    } finally {
      p.destroy();
    }
    return { done: false, value };
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an
 * :std:term:`asynchronous generator` (i.e., it is an instance of
 * :py:class:`~collections.abc.AsyncGenerator`)
 */
export class PyAsyncGenerator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_ASYNC_GENERATOR);
  }
}

export interface PyAsyncGenerator extends PyAsyncGeneratorMethods {}

export class PyAsyncGeneratorMethods {
  /**
   * Throws an exception into the Generator.
   *
   * See the documentation for :js:meth:`AsyncGenerator.throw`.
   *
   * @param exception Error The error to throw into the generator. Must be an
   * instanceof ``Error``.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  async throw(exc: any): Promise<IteratorResult<any, any>> {
    let idarg = Hiwire.new_value(exc);
    let idresult;
    try {
      Py_ENTER();
      idresult = Module.__pyproxyGen_athrow(_getPtr(this), idarg);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(idarg);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    const p = Hiwire.pop_value(idresult);
    let value;
    try {
      value = await p;
    } catch (e) {
      if (e && typeof e === "object") {
        if ((e as any).type === "StopAsyncIteration") {
          return { done: true, value };
        } else if ((e as any).type === "GeneratorExit") {
          return { done: true, value };
        }
      }
      throw e;
    } finally {
      p.destroy();
    }
    return { done: false, value };
  }

  /**
   * Throws a :py:exc:`GeneratorExit` into the generator and if the
   * :py:exc:`GeneratorExit` is not caught returns the argument value ``{done:
   * true, value: v}``. If the generator catches the :py:exc:`GeneratorExit` and
   * returns or yields another value the next value of the generator this is
   * returned in the normal way. If it throws some error other than
   * :py:exc:`GeneratorExit` or :py:exc:`StopAsyncIteration`, that error is
   * propagated. See the documentation for :js:meth:`AsyncGenerator.throw`
   *
   * @param any The value to return from the generator.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a :py:exc:`StopAsyncIteration`
   * exception, ``return`` returns ``{done : true, value : result_value}``.
   */
  async return(v: any): Promise<IteratorResult<any, any>> {
    let idresult;
    try {
      Py_ENTER();
      idresult = Module.__pyproxyGen_areturn(_getPtr(this));
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    const p = Hiwire.pop_value(idresult);
    let value;
    try {
      value = await p;
    } catch (e) {
      if (e && typeof e === "object") {
        if ((e as any).type === "StopAsyncIteration") {
          return { done: true, value };
        } else if ((e as any).type === "GeneratorExit") {
          return { done: true, value: v };
        }
      }
      throw e;
    } finally {
      p.destroy();
    }
    return { done: false, value };
  }
}

// Another layer of boilerplate. The PyProxyHandlers have some annoying logic
// to deal with straining out the spurious "Function" properties "prototype",
// "arguments", and "length", to deal with correctly satisfying the Proxy
// invariants, and to deal with the mro
function python_hasattr(jsobj: PyProxy, jskey: any) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Hiwire.new_value(jskey);
  let result;
  try {
    Py_ENTER();
    result = Module.__pyproxy_hasattr(ptrobj, idkey);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Hiwire.decref(idkey);
  }
  if (result === -1) {
    Module._pythonexc2js();
  }
  return result !== 0;
}

// Returns a JsRef in order to allow us to differentiate between "not found"
// (in which case we return 0) and "found 'None'" (in which case we return
// Js_undefined).
function python_getattr(jsobj: PyProxy, jskey: any) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Hiwire.new_value(jskey);
  let idresult;
  let cacheId = jsobj.$$.cache.cacheId;
  try {
    Py_ENTER();
    idresult = Module.__pyproxy_getattr(ptrobj, idkey, cacheId);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Hiwire.decref(idkey);
  }
  if (idresult === 0) {
    if (Module._PyErr_Occurred()) {
      Module._pythonexc2js();
    }
  }
  return idresult;
}

function python_setattr(jsobj: PyProxy, jskey: any, jsval: any) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Hiwire.new_value(jskey);
  let idval = Hiwire.new_value(jsval);
  let errcode;
  try {
    Py_ENTER();
    errcode = Module.__pyproxy_setattr(ptrobj, idkey, idval);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Hiwire.decref(idkey);
    Hiwire.decref(idval);
  }
  if (errcode === -1) {
    Module._pythonexc2js();
  }
}

function python_delattr(jsobj: PyProxy, jskey: any) {
  let ptrobj = _getPtr(jsobj);
  let idkey = Hiwire.new_value(jskey);
  let errcode;
  try {
    Py_ENTER();
    errcode = Module.__pyproxy_delattr(ptrobj, idkey);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Hiwire.decref(idkey);
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
  has(jsobj: PyProxy, jskey: any) {
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
  get(jsobj: PyProxy, jskey: any) {
    // Preference order:
    // 1. stuff from JavaScript
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
      return Hiwire.pop_value(idresult);
    }
  },
  set(jsobj: PyProxy, jskey: any, jsval: any) {
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
  deleteProperty(jsobj: PyProxy, jskey: any): boolean {
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
    // Otherwise JavaScript will throw a TypeError.
    return !descr || !!descr.configurable;
  },
  ownKeys(jsobj: PyProxy) {
    let ptrobj = _getPtr(jsobj);
    let idresult;
    try {
      Py_ENTER();
      idresult = Module.__pyproxy_ownKeys(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (idresult === 0) {
      Module._pythonexc2js();
    }
    let result = Hiwire.pop_value(idresult);
    result.push(...Reflect.ownKeys(jsobj));
    return result;
  },
  apply(jsobj: PyProxy & Function, jsthis: any, jsargs: any) {
    return jsobj.apply(jsthis, jsargs);
  },
};

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is :ref:`awaitable
 * <asyncio-awaitables>` (i.e., has an :meth:`~object.__await__` method).
 */
export class PyAwaitable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_AWAITABLE);
  }
}

export interface PyAwaitable extends Promise<any> {}
/** @deprecated Use :js:class:`pyodide.ffi.PyAwaitable` instead. */
export type PyProxyAwaitable = PyAwaitable;

/**
 * The Promise / JavaScript awaitable API.
 * @private
 */
export class PyAwaitableMethods {
  $$: any;
  /**
   * This wraps __pyproxy_ensure_future and makes a function that converts a
   * Python awaitable to a promise, scheduling the awaitable on the Python
   * event loop if necessary.
   * @private
   */
  _ensure_future(): Promise<any> {
    if (this.$$.promise) {
      return this.$$.promise;
    }
    let ptrobj = _getPtr(this);
    let resolveHandle;
    let rejectHandle;
    let promise = new Promise((resolve, reject) => {
      resolveHandle = resolve;
      rejectHandle = reject;
    });
    let resolve_handle_id = Hiwire.new_value(resolveHandle);
    let reject_handle_id = Hiwire.new_value(rejectHandle);
    let errcode;
    try {
      Py_ENTER();
      errcode = Module.__pyproxy_ensure_future(
        ptrobj,
        resolve_handle_id,
        reject_handle_id,
      );
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    } finally {
      Hiwire.decref(reject_handle_id);
      Hiwire.decref(resolve_handle_id);
    }
    if (errcode === -1) {
      Module._pythonexc2js();
    }
    this.$$.promise = promise;
    // @ts-ignore
    this.destroy();
    return promise;
  }
  /**
   * Calls :func:`asyncio.ensure_future` on the awaitable, executes
   * ``onFulfilled(result)`` when the :py:class:`~asyncio.Future` resolves successfully, executes
   * ``onRejected(error)`` when the :py:class:`~asyncio.Future` fails. Will be used implicitly by
   * ``await obj``.
   *
   * See the documentation for :js:meth:`Promise.then`.
   *
   * @param onFulfilled A handler called with the result as an argument if the
   * awaitable succeeds.
   * @param onRejected A handler called with the error as an argument if the
   * awaitable fails.
   * @returns The resulting Promise.
   */
  then(
    onFulfilled: (value: any) => any,
    onRejected: (reason: any) => any,
  ): Promise<any> {
    let promise = this._ensure_future();
    return promise.then(onFulfilled, onRejected);
  }
  /**
   * Calls :func:`asyncio.ensure_future` on the awaitable and executes
   * ``onRejected(error)`` if the :py:class:`~asyncio.Future` fails.
   *
   * See the documentation for :js:meth:`Promise.catch`.
   *
   * @param onRejected A handler called with the error as an argument if the
   * awaitable fails.
   * @returns The resulting Promise.
   */
  catch(onRejected: (reason: any) => any) {
    let promise = this._ensure_future();
    return promise.catch(onRejected);
  }
  /**
   * Calls :func:`asyncio.ensure_future` on the awaitable and executes
   * ``onFinally(error)`` when the :py:class:`~asyncio.Future` resolves.
   *
   * See the documentation for :js:meth:`Promise.finally`.
   *
   * @param onFinally A handler that is called with zero arguments when the
   * awaitable resolves.
   * @returns A Promise that resolves or rejects with the same result as the
   * original Promise, but only after executing the ``onFinally`` handler.
   */
  finally(onFinally: () => void) {
    let promise = this._ensure_future();
    return promise.finally(onFinally);
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is
 * :std:term:`callable` (i.e., has an :py:meth:`~operator.__call__` method).
 */
export class PyCallable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyCallable {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_CALLABLE);
  }
}

/**
 * @deprecated Use :js:class:`pyodide.ffi.PyCallable` instead.
 */
export type PyProxyCallable = PyCallable;

export interface PyCallable extends PyCallableMethods {
  (...args: any[]): any;
}

export class PyCallableMethods {
  /**
   * The ``apply()`` method calls the specified function with a given this
   * value, and arguments provided as an array (or an array-like object). Like
   * :js:meth:`Function.apply`.
   *
   * @param thisArg The ``this`` argument. Has no effect unless the
   * :js:class:`~pyodide.ffi.PyCallable` has :js:meth:`captureThis` set. If
   * :js:meth:`captureThis` is set, it will be passed as the first argument to
   * the Python function.
   * @param jsargs The array of arguments
   * @returns The result from the function call.
   */
  apply(thisArg: any, jsargs: any) {
    // Convert jsargs to an array using ordinary .apply in order to match the
    // behavior of .apply very accurately.
    jsargs = function (...args: any) {
      return args;
    }.apply(undefined, jsargs);
    jsargs = _adjustArgs(this, thisArg, jsargs);
    return Module.callPyObject(_getPtr(this), jsargs);
  }
  /**
   * Calls the function with a given this value and arguments provided
   * individually. See :js:meth:`Function.call`.
   *
   * @param thisArg The ``this`` argument. Has no effect unless the
   * :js:class:`~pyodide.ffi.PyCallable` has :js:meth:`captureThis` set. If
   * :js:meth:`captureThis` is set, it will be passed as the first argument to
   * the Python function.
   * @param jsargs The arguments
   * @returns The result from the function call.
   */
  call(thisArg: any, ...jsargs: any) {
    jsargs = _adjustArgs(this, thisArg, jsargs);
    return Module.callPyObject(_getPtr(this), jsargs);
  }
  /**
   * Call the function with key word arguments. The last argument must be an
   * object with the keyword arguments.
   */
  callKwargs(...jsargs: any) {
    if (jsargs.length === 0) {
      throw new TypeError(
        "callKwargs requires at least one argument (the key word argument object)",
      );
    }
    let kwargs = jsargs.pop();
    if (
      kwargs.constructor !== undefined &&
      kwargs.constructor.name !== "Object"
    ) {
      throw new TypeError("kwargs argument is not an object");
    }
    return Module.callPyObjectKwargs(_getPtr(this), jsargs, kwargs);
  }

  /**
   * The ``bind()`` method creates a new function that, when called, has its
   * ``this`` keyword set to the provided value, with a given sequence of
   * arguments preceding any provided when the new function is called. See
   * :js:meth:`Function.bind`.
   *
   * If the :js:class:`~pyodide.ffi.PyCallable` does not have
   * :js:meth:`captureThis` set, the ``this`` parameter will be discarded. If it
   * does have :js:meth:`captureThis` set, ``thisArg`` will be set to the first
   * argument of the Python function. The returned proxy and the original proxy
   * have the same lifetime so destroying either destroys both.
   *
   * @param thisArg The value to be passed as the ``this`` parameter to the
   * target function ``func`` when the bound function is called.
   * @param jsargs Extra arguments to prepend to arguments provided to the bound
   * function when invoking ``func``.
   * @returns
   */
  bind(thisArg: any, ...jsargs: any) {
    const self = this as unknown as PyProxy;
    const {
      boundArgs: boundArgsOld,
      boundThis: boundThisOld,
      isBound,
    } = self.$$props;
    let boundThis = thisArg;
    if (isBound) {
      boundThis = boundThisOld;
    }
    let boundArgs = boundArgsOld.concat(jsargs);
    const props: PyProxyProps = Object.assign({}, self.$$props, {
      boundArgs,
      isBound: true,
      boundThis,
    });
    const $$ = self.$$;
    let ptrobj = _getPtr(this);
    return pyproxy_new(ptrobj, { $$, flags: self.$$flags, props });
  }

  /**
   * Returns a :js:class:`~pyodide.ffi.PyProxy` that passes ``this`` as the first argument to the
   * Python function. The returned :js:class:`~pyodide.ffi.PyProxy` has the internal ``captureThis``
   * property set.
   *
   * It can then be used as a method on a JavaScript object. The returned proxy
   * and the original proxy have the same lifetime so destroying either destroys
   * both.
   *
   * For example:
   *
   * .. code-block:: pyodide
   *
   *    let obj = { a : 7 };
   *    pyodide.runPython(`
   *      def f(self):
   *        return self.a
   *    `);
   *    // Without captureThis, it doesn't work to use f as a method for obj:
   *    obj.f = pyodide.globals.get("f");
   *    obj.f(); // raises "TypeError: f() missing 1 required positional argument: 'self'"
   *    // With captureThis, it works fine:
   *    obj.f = pyodide.globals.get("f").captureThis();
   *    obj.f(); // returns 7
   *
   * @returns The resulting :js:class:`~pyodide.ffi.PyProxy`. It has the same lifetime as the
   * original :js:class:`~pyodide.ffi.PyProxy` but passes ``this`` to the wrapped function.
   *
   */
  captureThis(): PyProxy {
    const self = this as unknown as PyProxy;
    const props: PyProxyProps = Object.assign({}, self.$$props, {
      captureThis: true,
    });
    return pyproxy_new(_getPtr(this), {
      $$: self.$$,
      flags: self.$$flags,
      props,
    });
  }
}
// @ts-ignore
PyCallableMethods.prototype.prototype = Function.prototype;

// @ts-ignore
let type_to_array_map: Map<string, any> = new Map([
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
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object supports the
 * Python :external:doc:`c-api/buffer`.
 *
 * Examples of buffers include {py:class}`bytes` objects and numpy
 * {external+numpy:ref}`arrays`.
 */
export class PyBuffer extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyBuffer {
    return API.isPyProxy(obj) && !!(obj.$$flags & IS_BUFFER);
  }
}

export interface PyBuffer extends PyBufferMethods {}

export class PyBufferMethods {
  /**
   * Get a view of the buffer data which is usable from JavaScript. No copy is
   * ever performed.
   *
   * We do not support suboffsets, if the buffer requires suboffsets we will
   * throw an error. JavaScript nd array libraries can't handle suboffsets
   * anyways. In this case, you should use the :js:meth:`~PyProxy.toJs` api or
   * copy the buffer to one that doesn't use suboffsets (using e.g.,
   * :py:func:`numpy.ascontiguousarray`).
   *
   * If the buffer stores big endian data or half floats, this function will
   * fail without an explicit type argument. For big endian data you can use
   * :js:meth:`~PyProxy.toJs`. :js:class:`DataView` has support for big endian
   * data, so you might want to pass ``'dataview'`` as the type argument in that
   * case.
   *
   * @param type The type of the :js:attr:`~pyodide.ffi.PyBufferView.data` field
   * in the output. Should be one of: ``"i8"``, ``"u8"``, ``"u8clamped"``,
   * ``"i16"``, ``"u16"``, ``"i32"``, ``"u32"``, ``"i32"``, ``"u32"``,
   * ``"i64"``, ``"u64"``, ``"f32"``, ``"f64``, or ``"dataview"``. This argument
   * is optional, if absent :js:meth:`~pyodide.ffi.PyBuffer.getBuffer` will try
   * to determine the appropriate output type based on the buffer format string
   * (see :std:ref:`struct-format-strings`).
   */
  getBuffer(type?: string): PyBufferView {
    let ArrayType: any = undefined;
    if (type) {
      ArrayType = type_to_array_map.get(type);
      if (ArrayType === undefined) {
        throw new Error(`Unknown type ${type}`);
      }
    }
    let orig_stack_ptr = stackSave();
    let buffer_struct_ptr = stackAlloc(
      DEREF_U32(Module._buffer_struct_size, 0),
    );
    let this_ptr = _getPtr(this);
    let errcode;
    try {
      Py_ENTER();
      errcode = Module.__pyproxy_get_buffer(buffer_struct_ptr, this_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
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
    let shape = Hiwire.pop_value(DEREF_U32(buffer_struct_ptr, 6));
    let strides = Hiwire.pop_value(DEREF_U32(buffer_struct_ptr, 7));

    let view_ptr = DEREF_U32(buffer_struct_ptr, 8);
    let c_contiguous = !!DEREF_U32(buffer_struct_ptr, 9);
    let f_contiguous = !!DEREF_U32(buffer_struct_ptr, 10);

    let format = Module.UTF8ToString(format_ptr);
    stackRestore(orig_stack_ptr);

    let success = false;
    try {
      let bigEndian = false;
      if (ArrayType === undefined) {
        [ArrayType, bigEndian] = Module.processBufferFormatString(
          format,
          " In this case, you can pass an explicit type argument.",
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
            "to little endian.",
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
          `Buffer does not have valid alignment for a ${ArrayType.name}`,
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
        PyBufferView.prototype,
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
        }),
      );
      // Module.bufferFinalizationRegistry.register(result, view_ptr, result);
      return result;
    } finally {
      if (!success) {
        try {
          Py_ENTER();
          Module._PyBuffer_Release(view_ptr);
          Module._PyMem_Free(view_ptr);
          Py_EXIT();
        } catch (e) {
          API.fatal_error(e);
        }
      }
    }
  }
}

export type TypedArray =
  | Int8Array
  | Uint8Array
  | Int16Array
  | Uint16Array
  | Int32Array
  | Uint32Array
  | Uint8ClampedArray
  | Float32Array
  | Float64Array;

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is a :py:class:`dict`.
 */
export class PyDict extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    // TODO: allow MutableMappings?
    return API.isPyProxy(obj) && obj.type === "dict";
  }
}

export interface PyDict
  extends PyProxyWithGet,
    PyProxyWithSet,
    PyProxyWithHas,
    PyProxyWithLength,
    PyIterable {}

/** @deprecated Use :js:class:`pyodide.ffi.PyDict` instead. */
export type PyProxyDict = PyDict;

/**
 * A class to allow access to Python data buffers from JavaScript. These are
 * produced by :js:meth:`~pyodide.ffi.PyBuffer.getBuffer` and cannot be constructed directly.
 * When you are done, release it with the :js:func:`~PyBufferView.release` method.
 * See the Python :external:doc:`c-api/buffer` documentation for more
 * information.
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
export class PyBufferView {
  /**
   * The offset of the first entry of the array. For instance if our array
   * is 3d, then you will find ``array[0,0,0]`` at
   * ``pybuf.data[pybuf.offset]``
   */
  offset: number;

  /**
   * If the data is read only, you should not modify it. There is no way for us
   * to enforce this, but it may cause very weird behavior. See
   * :py:attr:`memoryview.readonly`.
   */
  readonly: boolean;

  /**
   * The format string for the buffer. See :ref:`struct-format-strings`
   * and :py:attr:`memoryview.format`.
   */
  format: string;

  /**
   * How large is each entry in bytes? See :py:attr:`memoryview.itemsize`.
   */
  itemsize: number;

  /**
   * The number of dimensions of the buffer. If ``ndim`` is 0, the buffer
   * represents a single scalar or struct. Otherwise, it represents an
   * array. See :py:attr:`memoryview.ndim`.
   */
  ndim: number;

  /**
   * The total number of bytes the buffer takes up. This is equal to
   * :js:attr:`buff.data.byteLength <TypedArray.byteLength>`. See :py:attr:`memoryview.nbytes`.
   */
  nbytes: number;

  /**
   * The shape of the buffer, that is how long it is in each dimension.
   * The length will be equal to ``ndim``. For instance, a 2x3x4 array
   * would have shape ``[2, 3, 4]``. See :py:attr:`memoryview.shape`.
   */
  shape: number[];

  /**
   * An array of of length ``ndim`` giving the number of elements to skip
   * to get to a new element in each dimension. See the example definition
   * of a ``multiIndexToIndex`` function above. See :py:attr:`memoryview.strides`.
   */
  strides: number[];

  /**
   * The actual data. A typed array of an appropriate size backed by a segment
   * of the WASM memory.
   *
   * The ``type`` argument of :js:meth:`~pyodide.ffi.PyBuffer.getBuffer` determines
   * which sort of :js:class:`TypedArray` or :js:class:`DataView` to return. By
   * default :js:meth:`~pyodide.ffi.PyBuffer.getBuffer` will look at the format string
   * to determine the most appropriate option. Most often the result is a
   * :js:class:`Uint8Array`.
   *
   * .. admonition:: Contiguity
   *    :class: warning
   *
   *    If the buffer is not contiguous, the :js:attr:`~PyBufferView.readonly`
   *    TypedArray will contain data that is not part of the buffer. Modifying
   *    this data leads to undefined behavior.
   *
   * .. admonition:: Read only buffers
   *    :class: warning
   *
   *    If :js:attr:`buffer.readonly <PyBufferView.readonly>` is ``true``, you
   *    should not modify the buffer. Modifying a read only buffer leads to
   *    undefined behavior.
   *
   */
  data: TypedArray;

  /**
   * Is it C contiguous? See :py:attr:`memoryview.c_contiguous`.
   */
  c_contiguous: boolean;

  /**
   * Is it Fortran contiguous? See :py:attr:`memoryview.f_contiguous`.
   */
  f_contiguous: boolean;

  /** @private */
  _released: boolean;

  /** @private */
  _view_ptr: number;

  /** @private */
  constructor() {
    throw new TypeError("PyBufferView is not a constructor");
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
      Py_ENTER();
      Module._PyBuffer_Release(this._view_ptr);
      Module._PyMem_Free(this._view_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    this._released = true;
    // @ts-ignore
    this.data = null;
  }
}
