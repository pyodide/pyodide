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

declare var Tests: any;
declare var Module: any;

import { TypedArray } from "types";
import { warnOnce } from "pyodide-util";

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
declare var IS_SEQUENCE: number;
declare var IS_MUTABLE_SEQUENCE: number;
declare var IS_JSON_ADAPTOR_DICT: number;
declare var IS_JSON_ADAPTOR_SEQUENCE: number;

declare function DEREF_U32(ptr: number, offset: number): number;
declare function Py_ENTER(): void;
declare function Py_EXIT(): void;
// end-pyodide-skip

function isPyProxy(jsobj: any): jsobj is PyProxy {
  try {
    return jsobj instanceof PyProxy;
  } catch (e) {
    return false;
  }
}
API.isPyProxy = isPyProxy;

declare var FinalizationRegistry: any;
declare var globalThis: any;

if (globalThis.FinalizationRegistry) {
  Module.finalizationRegistry = new FinalizationRegistry(
    ({ ptr, cache }: PyProxyShared) => {
      if (cache) {
        // If we leak a proxy, we must transitively leak everything in its cache
        // too =(
        cache.leaked = true;
        pyproxy_decref_cache(cache);
      }
      try {
        Py_ENTER();
        _Py_DecRef(ptr);
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
  //     _PyBuffer_Release(ptr);
  //     _PyMem_Free(ptr);
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

type PyProxyCache = {
  map: Map<string, any>;
  json_adaptor_map: Map<string, any>;
  refcnt: number;
  leaked?: boolean;
};
type PyProxyShared = {
  ptr: number;
  cache: PyProxyCache;
  flags: number;
  promise: Promise<any> | undefined;
  destroyed_msg: string | undefined;
  gcRegistered: boolean;
};
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

type PyProxyAttrs = {
  // shared between aliases but not between copies
  shared: PyProxyShared;
  // properties that may be different between aliases
  props: PyProxyProps;
};

const pyproxyAttrsSymbol = Symbol("pyproxy.attrs");
function pyproxy_getflags(ptrobj: number, is_json_adaptor: boolean) {
  Py_ENTER();
  try {
    return _pyproxy_getflags(ptrobj, is_json_adaptor);
  } finally {
    Py_EXIT();
  }
}

/**
 * Create a new PyProxy wrapping ptrobj which is a PyObject*.
 *
 * Two proxies are **aliases** if they share `shared` (they may have different
 * props). Aliases are created by `bind` and `captureThis`. Aliases share the
 * same lifetime: `destroy` destroys both of them, they are only registered with
 * the garbage collector once, they only own a single refcount.  An **alias** is
 * created by passing the shared option.
 *
 * Two proxies are **copies** if they share `shared.cache`. Two copies share
 * attribute caches but they otherwise have independent lifetimes. The attribute
 * caches are refcounted so that they can be cleaned up when all copies are
 * destroyed. A **copy** is made by passing the `cache` argument.
 *
 * In the case that the Python object is callable, PyProxy inherits from
 * Function so that PyProxy objects can be callable. In that case we MUST expose
 * certain properties inherited from Function, but we do our best to remove as
 * many as possible.
 */
function pyproxy_new(
  ptr: number,
  {
    flags: flags_arg,
    cache,
    props,
    shared,
    gcRegister,
    jsonAdaptor,
  }: {
    flags?: number;
    cache?: PyProxyCache;
    shared?: PyProxyShared;
    props?: any;
    gcRegister?: boolean;
    jsonAdaptor?: boolean;
  } = {},
): PyProxy {
  if (gcRegister === undefined) {
    // register by default
    gcRegister = true;
  }
  const flags =
    flags_arg !== undefined ? flags_arg : pyproxy_getflags(ptr, !!jsonAdaptor);
  if (flags === -1) {
    _pythonexc2js();
  }
  const is_sequence = flags & IS_SEQUENCE;
  const is_dict_adaptor = flags & IS_JSON_ADAPTOR_DICT;
  const cls = Module.getPyProxyClass(flags);
  let target: any;
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

  const isAlias = !!shared;
  if (!shared) {
    // Not an alias so we have to make `shared`.
    if (!cache) {
      // In this case it's not a copy.
      cache = { map: new Map(), json_adaptor_map: new Map(), refcnt: 0 };
    }
    cache.refcnt++;
    shared = {
      ptr,
      cache,
      flags,
      promise: undefined,
      destroyed_msg: undefined,
      gcRegistered: false,
    };
    _Py_IncRef(ptr);
  }

  props = Object.assign(
    { isBound: false, captureThis: false, boundArgs: [], roundtrip: false },
    props,
  );
  let handlers;
  if (is_dict_adaptor) {
    handlers = PyProxyJsonAdaptorDictHandlers;
  } else if (is_sequence) {
    handlers = PyProxySequenceHandlers;
  } else {
    handlers = PyProxyHandlers;
  }
  let proxy = new Proxy(target, handlers);
  if (!isAlias && gcRegister) {
    // we need to register only once for a set of aliases. we can't register the
    // proxy directly since that isn't shared between aliases. The aliases all
    // share $$ so we can register that. They also need access to the data in
    // $$, but we can't use $$ itself as the held object since that would keep
    // $$ from being gc'd ever. So we make a copy. To prevent double free, we
    // have to be careful to unregister when we destroy.
    gc_register_proxy(shared);
  }
  if (!isAlias) {
    trace_pyproxy_alloc(proxy);
  }
  const attrs = { shared, props };
  target[pyproxyAttrsSymbol] = attrs;
  return proxy;
}
Module.pyproxy_new = pyproxy_new;

function gc_register_proxy(shared: PyProxyShared) {
  const shared_copy = Object.assign({}, shared);
  shared.gcRegistered = true;
  Module.finalizationRegistry.register(shared, shared_copy, shared);
}
Module.gc_register_proxy = gc_register_proxy;

function _getAttrsQuiet(jsobj: any): PyProxyAttrs {
  return jsobj[pyproxyAttrsSymbol];
}
Module.PyProxy_getAttrsQuiet = _getAttrsQuiet;
function _getAttrs(jsobj: any): PyProxyAttrs {
  const attrs = _getAttrsQuiet(jsobj);
  if (!attrs.shared.ptr) {
    throw new Error(attrs.shared.destroyed_msg);
  }
  return attrs;
}
Module.PyProxy_getAttrs = _getAttrs;

function _getPtr(jsobj: any) {
  return _getAttrs(jsobj).shared.ptr;
}

function _getFlags(jsobj: any): number {
  return Object.getPrototypeOf(jsobj).$$flags;
}

function isJsonAdaptor(jsobj: any): boolean {
  return !!(
    _getFlags(jsobj) &
    (IS_JSON_ADAPTOR_SEQUENCE | IS_JSON_ADAPTOR_DICT)
  );
}

function _adjustArgs(proxyobj: any, jsthis: any, jsargs: any[]): any[] {
  const { captureThis, boundArgs, boundThis, isBound } =
    _getAttrs(proxyobj).props;
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
    [IS_SEQUENCE, PySequenceMethods],
    [IS_MUTABLE_SEQUENCE, PyMutableSequenceMethods],
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
  if (flags & IS_SEQUENCE || flags & HAS_GET) {
    Object.assign(
      descriptors,
      Object.getOwnPropertyDescriptors(PyAsJsonAdaptorMethods.prototype),
    );
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
  const super_proto = flags & IS_CALLABLE ? PyProxyFunctionProto : PyProxyProto;
  const sub_proto = Object.create(super_proto, descriptors);
  function NewPyProxyClass() {}
  NewPyProxyClass.prototype = sub_proto;
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
  if (cache.leaked) {
    return;
  }
  if (cache.refcnt === 0) {
    for (const proxy of cache.map.values()) {
      Module.pyproxy_destroy(proxy, pyproxy_cache_destroyed_msg, true);
    }
    for (const proxy of cache.json_adaptor_map.values()) {
      Module.pyproxy_destroy(proxy, pyproxy_cache_destroyed_msg, true);
    }
  }
}

function generateDestroyedMessage(
  proxy: PyProxy,
  destroyed_msg: string,
): string {
  destroyed_msg = destroyed_msg || "Object has already been destroyed";
  if (API.debug_ffi) {
    let proxy_type = proxy.type;
    let proxy_repr;
    try {
      proxy_repr = proxy.toString();
    } catch (e) {
      if ((e as any).pyodide_fatal_error) {
        throw e;
      }
    }
    destroyed_msg += "\n" + `The object was of type "${proxy_type}" and `;
    if (proxy_repr) {
      destroyed_msg += `had repr "${proxy_repr}"`;
    } else {
      destroyed_msg += "an error was raised when trying to generate its repr";
    }
  } else {
    destroyed_msg +=
      "\n" +
      "For more information about the cause of this error, use `pyodide.setDebug(true)`";
  }
  return destroyed_msg;
}

Module.pyproxy_destroy = function (
  proxy: PyProxy,
  destroyed_msg: string,
  destroy_roundtrip: boolean,
) {
  const { shared, props } = _getAttrsQuiet(proxy);
  if (!shared.ptr) {
    // already destroyed
    return;
  }
  if (!destroy_roundtrip && props.roundtrip) {
    return;
  }
  shared.destroyed_msg = generateDestroyedMessage(proxy, destroyed_msg);
  // Maybe the destructor will call JavaScript code that will somehow try
  // to use this proxy. Mark it deleted before decrementing reference count
  // just in case!
  const ptr = shared.ptr;
  shared.ptr = 0;
  if (shared.gcRegistered) {
    Module.finalizationRegistry.unregister(shared);
  }
  pyproxy_decref_cache(shared.cache);

  try {
    Py_ENTER();
    _Py_DecRef(ptr);
    trace_pyproxy_dealloc(proxy);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
};

// Now a lot of boilerplate to wrap the abstract Object protocol wrappers
// defined in pyproxy.c in JavaScript functions.

function callPyObjectKwargs(ptrobj: number, jsargs: any[], kwargs: any) {
  // We don't do any checking for kwargs, checks are in PyProxy.callKwargs
  // which only is used when the keyword arguments come from the user.
  const num_pos_args = jsargs.length;
  const kwargs_names = Object.keys(kwargs);
  const kwargs_values = Object.values(kwargs);
  const num_kwargs = kwargs_names.length;
  jsargs.push(...kwargs_values);

  let result;
  try {
    Py_ENTER();
    result = __pyproxy_apply(
      ptrobj,
      jsargs,
      num_pos_args,
      kwargs_names,
      num_kwargs,
    );
    Py_EXIT();
  } catch (e) {
    API.maybe_fatal_error(e);
    return;
  }
  if (result === null) {
    _pythonexc2js();
  }
  // Automatically schedule coroutines
  if (result && result.type === "coroutine" && result._ensure_future) {
    Py_ENTER();
    const is_coroutine = __iscoroutinefunction(ptrobj);
    Py_EXIT();
    if (is_coroutine) {
      result._ensure_future();
    }
  }
  return result;
}

/**
 * A version of callPyObjectKwargs that supports the JSPI.
 *
 * It returns a promise. Inside Python, JS promises can be syncified, which
 * switches the stack to synchronously wait for them to be resolved.
 *
 * Pretty much everything is the same as callPyObjectKwargs except we use the
 * special JSPI-friendly promisingApply wrapper of `__pyproxy_apply`. This
 * causes the VM to invent a suspender and call a wrapper module which stores it
 * into suspenderGlobal (for later use by JsvPromise_syncify). Then it calls
 * _pyproxy_apply with the same arguments we gave to `promisingApply`.
 */
async function callPyObjectKwargsPromising(
  ptrobj: number,
  jsargs: any,
  kwargs: any,
) {
  if (!Module.jspiSupported) {
    throw new Error(
      "WebAssembly stack switching not supported in this JavaScript runtime",
    );
  }
  // We don't do any checking for kwargs, checks are in PyProxy.callKwargs
  // which only is used when the keyword arguments come from the user.
  const num_pos_args = jsargs.length;
  const kwargs_names = Object.keys(kwargs);
  const kwargs_values = Object.values(kwargs);
  const num_kwargs = kwargs_names.length;
  jsargs.push(...kwargs_values);

  const stackTop = stackSave();
  const exc = stackAlloc(4);
  let result;
  try {
    Py_ENTER();
    // promisingApply clears the error flag and saves any error into excStatus.
    // This ensures that tasks that are run between when promisingApply resolves
    // and when this task resumes here won't incorrectly observe the error flag.
    // See test_stack_switching.test_throw_from_switcher for a detailed explanation.
    result = await Module.promisingApply(
      ptrobj,
      jsargs,
      num_pos_args,
      kwargs_names,
      num_kwargs,
      exc,
    );
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (result === null) {
    _PyErr_SetRaisedException(HEAPU32[exc / 4]);
    try {
      _pythonexc2js();
    } finally {
      stackRestore(stackTop);
    }
  }
  // Automatically schedule coroutines
  if (result && result.type === "coroutine" && result._ensure_future) {
    Py_ENTER();
    const is_coroutine = __iscoroutinefunction(ptrobj);
    Py_EXIT();
    if (is_coroutine) {
      result._ensure_future();
    }
  }
  return result;
}

Module.callPyObjectMaybePromising = async function (
  ptrobj: number,
  jsargs: any,
) {
  if (Module.jspiSupported) {
    return await callPyObjectKwargsPromising(ptrobj, jsargs, {});
  }
  return callPyObjectKwargs(ptrobj, jsargs, {});
};

Module.callPyObject = function (ptrobj: number, jsargs: any) {
  return callPyObjectKwargs(ptrobj, jsargs, {});
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
  $$flags: number;

  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return [PyProxy, PyProxyFunction].some((cls) =>
      Function.prototype[Symbol.hasInstance].call(cls, obj),
    );
  }

  /**
   * @hideconstructor
   */
  constructor() {
    throw new TypeError("PyProxy is not a constructor");
  }

  /** @hidden */
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
    return __pyproxy_type(ptrobj);
  }
  /**
   * Returns `str(o)` (unless `pyproxyToStringRepr: true` was passed to
   * :js:func:`~globalThis.loadPyodide` in which case it will return `repr(o)`)
   */
  toString(): string {
    let ptrobj = _getPtr(this);
    let result;
    try {
      Py_ENTER();
      result = __pyproxy_repr(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    return result;
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
    let attrs = _getAttrs(this);
    return pyproxy_new(attrs.shared.ptr, {
      flags: _getFlags(this),
      cache: attrs.shared.cache,
      props: attrs.props,
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
    let result;
    let proxies;
    if (!create_pyproxies) {
      proxies = null;
    } else if (pyproxies) {
      proxies = pyproxies;
    } else {
      proxies = [];
    }
    try {
      Py_ENTER();
      result = _python2js_custom(
        ptrobj,
        depth,
        proxies,
        dict_converter || null,
        default_converter || null,
      );
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    return result;
  }
}

const PyProxyProto = PyProxy.prototype;
// For some weird reason in the node and firefox tests, the identity of
// `Function` changes between now and the test suite. Can't reproduce this
// outside the test suite though...
// See test_pyproxy_instanceof_function.
Tests.Function = Function;
const PyProxyFunctionProto = Object.create(
  Function.prototype,
  Object.getOwnPropertyDescriptors(PyProxyProto),
);
function PyProxyFunction() {}
PyProxyFunction.prototype = PyProxyFunctionProto;

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a :meth:`~object.__len__`
 * method.
 */
export class PyProxyWithLength extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & HAS_LENGTH);
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
      length = _PyObject_Size(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (length === -1) {
      _pythonexc2js();
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
    return API.isPyProxy(obj) && !!(_getFlags(obj) & HAS_GET);
  }
}

export interface PyProxyWithGet extends PyGetItemMethods {}

class PyAsJsonAdaptorMethods {
  asJsJson() {
    let { shared, props } = _getAttrs(this);
    let flags = _getFlags(this);
    if (flags & IS_SEQUENCE) {
      flags |= IS_JSON_ADAPTOR_SEQUENCE;
    } else {
      flags |= IS_JSON_ADAPTOR_DICT;
    }
    return pyproxy_new(shared.ptr, {
      shared,
      flags,
      props,
    });
  }
}

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
    const { shared } = _getAttrs(this);
    let result;
    try {
      Py_ENTER();
      // Cache is only used if isJsonAdaptor is true.
      result = __pyproxy_getitem(
        shared.ptr,
        key,
        shared.cache.json_adaptor_map,
        isJsonAdaptor(this),
      );
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      if (_PyErr_Occurred()) {
        _pythonexc2js();
      } else {
        return undefined;
      }
    }
    return result;
  }
  /**
   * Returns the object treated as a json adaptor.
   *
   * With a JsonAdaptor:
   *  1. property access / modification / deletion is implemented with
   *     :meth:`~object.__getitem__`, :meth:`~object.__setitem__`, and
   *     :meth:`~object.__delitem__` respectively.
   *  2. If an attribute is accessed and the result implements
   *     :meth:`~object.__getitem__` then the result will also be a json
   *     adaptor.
   *
   * For instance, ``JSON.stringify(proxy.asJsJson())`` acts like an
   * inverse to Python's :py:func:`json.loads`.
   */
  asJsJson(): PyProxy & {} {
    // This is just here for the docs. The actual implementation comes from
    // PyAsJsonAdaptorMethods.
    throw new Error("Should not happen");
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object has a
 * :meth:`~object.__setitem__` or :meth:`~object.__delitem__` method.
 */
export class PyProxyWithSet extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & HAS_SET);
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
    let err;
    try {
      Py_ENTER();
      err = __pyproxy_setitem(ptrobj, key, value);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (err === -1) {
      _pythonexc2js();
    }
  }
  /**
   * This translates to the Python code ``del obj[key]``.
   *
   * @param key The key to delete.
   */
  delete(key: any) {
    let ptrobj = _getPtr(this);
    let err;
    try {
      Py_ENTER();
      err = __pyproxy_delitem(ptrobj, key);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (err === -1) {
      _pythonexc2js();
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
    return API.isPyProxy(obj) && !!(_getFlags(obj) & HAS_CONTAINS);
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
    let result;
    try {
      Py_ENTER();
      result = __pyproxy_contains(ptrobj, key);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === -1) {
      _pythonexc2js();
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
 */
function* iter_helper(
  iterptr: number,
  token: {},
  proxyCache: Map<string, any>,
  is_json_adaptor: boolean,
): Generator<any> {
  const to_destroy = [];
  try {
    while (true) {
      Py_ENTER();
      const item = __pyproxy_iter_next(iterptr, proxyCache, is_json_adaptor);
      if (item === null) {
        break;
      }
      Py_EXIT();
      yield item;
      // If it's a json adaptor, we cached the result so we don't need to
      // destroy it (they'll get destroyed when we destroy the root).
      // This is necessary to get JSON.stringify to work correctly.
      if (!is_json_adaptor && API.isPyProxy(item)) {
        to_destroy.push(item);
      }
    }
  } catch (e) {
    API.fatal_error(e);
  } finally {
    Module.finalizationRegistry.unregister(token);
    _Py_DecRef(iterptr);
  }
  try {
    to_destroy.forEach((e) =>
      Module.pyproxy_destroy(
        e,
        "This borrowed proxy was automatically destroyed when an iterator was exhausted.",
      ),
    );
  } catch (e) {}
  if (_PyErr_Occurred()) {
    _pythonexc2js();
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is :std:term:`iterable`
 * (i.e., it has an :meth:`~object.__iter__` method).
 */
export class PyIterable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return (
      API.isPyProxy(obj) && !!(_getFlags(obj) & (IS_ITERABLE | IS_ITERATOR))
    );
  }
}

export interface PyIterable extends PyIterableMethods {}

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
    const { shared } = _getAttrs(this);
    let token = {};
    let iterptr;
    try {
      Py_ENTER();
      iterptr = _PyObject_GetIter(shared.ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (iterptr === 0) {
      _pythonexc2js();
    }

    // Cache is only used if isJsonAdaptor is true.
    let result = iter_helper(
      iterptr,
      token,
      shared.cache.json_adaptor_map,
      isJsonAdaptor(this),
    );
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
 */
async function* aiter_helper(iterptr: number, token: {}): AsyncGenerator<any> {
  try {
    while (true) {
      let p;
      try {
        Py_ENTER();
        p = __pyproxy_aiter_next(iterptr);
        Py_EXIT();
        if (p === null) {
          break;
        }
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
    _Py_DecRef(iterptr);
  }
  if (_PyErr_Occurred()) {
    _pythonexc2js();
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
      !!(_getFlags(obj) & (IS_ASYNC_ITERABLE | IS_ASYNC_ITERATOR))
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
      iterptr = _PyObject_GetAIter(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (iterptr === 0) {
      _pythonexc2js();
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
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_ITERATOR);
  }
}

export interface PyIterator extends PyIteratorMethods {}

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
   * @param arg The value to send to the generator. The value will be assigned
   * as a result of a yield expression.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``next`` returns ``{done : false, value :
   * some_value}``. When the generator raises a :py:exc:`StopIteration`
   * exception, ``next`` returns ``{done : true, value : result_value}``.
   */
  next(arg: any = undefined): IteratorResult<any, any> {
    // Note: arg is optional, if arg is not supplied, it will be undefined
    // which gets converted to "Py_None". This is as intended.
    let result;
    let done;
    try {
      Py_ENTER();
      result = __pyproxyGen_Send(_getPtr(this), arg);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    return result;
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is a :std:term:`generator`
 * (i.e., it is an instance of :py:class:`~collections.abc.Generator`).
 */
export class PyGenerator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_GENERATOR);
  }
}

export interface PyGenerator extends PyGeneratorMethods {}

export class PyGeneratorMethods {
  /**
   * Throws an exception into the Generator.
   *
   * See the documentation for :js:meth:`Generator.throw`.
   *
   * @param exc Error The error to throw into the generator. Must be an
   * instanceof ``Error``.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  throw(exc: any): IteratorResult<any, any> {
    let result;
    try {
      Py_ENTER();
      result = __pyproxyGen_throw(_getPtr(this), exc);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    return result;
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
   * @param v The value to return from the generator.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  return(v: any): IteratorResult<any, any> {
    // Note: arg is optional, if arg is not supplied, it will be undefined
    // which gets converted to "Py_None". This is as intended.
    let result: IteratorResult<any, any>;
    try {
      Py_ENTER();
      result = __pyproxyGen_return(_getPtr(this), v);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    return result;
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an
 * :std:term:`asynchronous iterator`
 */
export class PyAsyncIterator extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_ASYNC_ITERATOR);
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
   * @param arg The value to send to a generator. The value will be assigned as
   * a result of a yield expression.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * iterator yields ``some_value``, ``next`` returns ``{done : false, value :
   * some_value}``. When the giterator is done, ``next`` returns
   * ``{done : true }``.
   */
  async next(arg: any = undefined): Promise<IteratorResult<any, any>> {
    let p;
    try {
      Py_ENTER();
      p = __pyproxyGen_asend(_getPtr(this), arg);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (p === null) {
      _pythonexc2js();
    }
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
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_ASYNC_GENERATOR);
  }
}

export interface PyAsyncGenerator extends PyAsyncGeneratorMethods {}

export class PyAsyncGeneratorMethods {
  /**
   * Throws an exception into the Generator.
   *
   * See the documentation for :js:meth:`AsyncGenerator.throw`.
   *
   * @param exc Error The error to throw into the generator. Must be an
   * instanceof ``Error``.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a
   * ``StopIteration(result_value)`` exception, ``return`` returns ``{done :
   * true, value : result_value}``.
   */
  async throw(exc: any): Promise<IteratorResult<any, any>> {
    let p;
    try {
      Py_ENTER();
      p = __pyproxyGen_athrow(_getPtr(this), exc);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (p === null) {
      _pythonexc2js();
    }
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
   * @param v The value to return from the generator.
   * @returns An Object with two properties: ``done`` and ``value``. When the
   * generator yields ``some_value``, ``return`` returns ``{done : false, value
   * : some_value}``. When the generator raises a :py:exc:`StopAsyncIteration`
   * exception, ``return`` returns ``{done : true, value : result_value}``.
   */
  async return(v: any): Promise<IteratorResult<any, any>> {
    let p;
    try {
      Py_ENTER();
      p = __pyproxyGen_areturn(_getPtr(this));
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (p === null) {
      _pythonexc2js();
    }
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

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an
 * :py:class:`~collections.abc.Sequence` (i.e., a :py:class:`list`)
 */
export class PySequence extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_SEQUENCE);
  }
}

export interface PySequence extends PySequenceMethods {}

// JS default comparison is to convert to strings and compare lexicographically
function defaultCompareFunc(a: any, b: any): number {
  const astr = a.toString();
  const bstr = b.toString();
  if (astr === bstr) {
    return 0;
  }
  if (astr < bstr) {
    return -1;
  }
  return 1;
}

// Missing:
// flatMap, flat,
export class PySequenceMethods {
  /** @hidden */
  get [Symbol.isConcatSpreadable]() {
    return true;
  }
  /**
   * See :js:meth:`Array.join`. The :js:meth:`Array.join` method creates and
   * returns a new string by concatenating all of the elements in the
   * :py:class:`~collections.abc.Sequence`.
   *
   * @param separator A string to separate each pair of adjacent elements of the
   * Sequence.
   *
   * @returns  A string with all Sequence elements joined.
   */
  join(separator?: string) {
    return Array.prototype.join.call(this, separator);
  }
  /**
   * See :js:meth:`Array.slice`. The :js:meth:`Array.slice` method returns a
   * shallow copy of a portion of a :py:class:`~collections.abc.Sequence` into a
   * new array object selected from ``start`` to ``stop`` (`stop` not included)
   * @param start Zero-based index at which to start extraction. Negative index
   * counts back from the end of the Sequence.
   * @param stop Zero-based index at which to end extraction. Negative index
   * counts back from the end of the Sequence.
   * @returns A new array containing the extracted elements.
   */
  slice(start?: number, stop?: number): any {
    return Array.prototype.slice.call(this, start, stop);
  }
  /**
   * See :js:meth:`Array.lastIndexOf`. Returns the last index at which a given
   * element can be found in the Sequence, or -1 if it is not present.
   * @param elt Element to locate in the Sequence.
   * @param fromIndex Zero-based index at which to start searching backwards,
   * converted to an integer. Negative index counts back from the end of the
   * Sequence.
   * @returns The last index of the element in the Sequence; -1 if not found.
   */
  lastIndexOf(elt: any, fromIndex?: number) {
    if (fromIndex === undefined) {
      fromIndex = (this as any).length;
    }
    return Array.prototype.lastIndexOf.call(this, elt, fromIndex);
  }
  /**
   * See :js:meth:`Array.indexOf`. Returns the first index at which a given
   * element can be found in the Sequence, or -1 if it is not present.
   * @param elt Element to locate in the Sequence.
   * @param fromIndex Zero-based index at which to start searching, converted to
   * an integer. Negative index counts back from the end of the Sequence.
   * @returns The first index of the element in the Sequence; -1 if not found.
   */
  indexOf(elt: any, fromIndex?: number) {
    return Array.prototype.indexOf.call(this, elt, fromIndex);
  }
  /**
   * See :js:meth:`Array.forEach`. Executes a provided function once for each
   * ``Sequence`` element.
   * @param callbackfn A function to execute for each element in the ``Sequence``. Its
   * return value is discarded.
   * @param thisArg A value to use as ``this`` when executing ``callbackFn``.
   */
  forEach(callbackfn: (elt: any) => void, thisArg?: any) {
    Array.prototype.forEach.call(this, callbackfn, thisArg);
  }
  /**
   * See :js:meth:`Array.map`. Creates a new array populated with the results of
   * calling a provided function on every element in the calling ``Sequence``.
   * @param callbackfn A function to execute for each element in the ``Sequence``. Its
   * return value is added as a single element in the new array.
   * @param thisArg A value to use as ``this`` when executing ``callbackFn``.
   */
  map<U>(
    callbackfn: (elt: any, index: number, array: any) => U,
    thisArg?: any,
  ): U[] {
    // @ts-ignore
    return Array.prototype.map.call(this, callbackfn, thisArg);
  }
  /**
   * See :js:meth:`Array.filter`. Creates a shallow copy of a portion of a given
   * ``Sequence``, filtered down to just the elements from the given array that pass
   * the test implemented by the provided function.
   * @param predicate A function to execute for each element in the array. It
   * should return a truthy value to keep the element in the resulting array,
   * and a falsy value otherwise.
   * @param thisArg A value to use as ``this`` when executing ``predicate``.
   */
  filter(
    predicate: (elt: any, index: number, array: any) => boolean,
    thisArg?: any,
  ) {
    return Array.prototype.filter.call(this, predicate, thisArg);
  }
  /**
   * See :js:meth:`Array.some`. Tests whether at least one element in the
   * ``Sequence`` passes the test implemented by the provided function.
   * @param predicate A function to execute for each element in the
   * ``Sequence``. It should return a truthy value to indicate the element
   * passes the test, and a falsy value otherwise.
   * @param thisArg A value to use as ``this`` when executing ``predicate``.
   */
  some(
    predicate: (value: any, index: number, array: any[]) => unknown,
    thisArg?: any,
  ): boolean {
    return Array.prototype.some.call(this, predicate, thisArg);
  }
  /**
   * See :js:meth:`Array.every`. Tests whether every element in the ``Sequence``
   * passes the test implemented by the provided function.
   * @param predicate A function to execute for each element in the
   * ``Sequence``. It should return a truthy value to indicate the element
   * passes the test, and a falsy value otherwise.
   * @param thisArg A value to use as ``this`` when executing ``predicate``.
   */
  every(
    predicate: (value: any, index: number, array: any[]) => unknown,
    thisArg?: any,
  ): boolean {
    return Array.prototype.every.call(this, predicate, thisArg);
  }
  /**
   * See :js:meth:`Array.reduce`. Executes a user-supplied "reducer" callback
   * function on each element of the Sequence, in order, passing in the return
   * value from the calculation on the preceding element. The final result of
   * running the reducer across all elements of the Sequence is a single value.
   * @param callbackfn A function to execute for each element in the ``Sequence``. Its
   * return value is discarded.
   */
  reduce(
    callbackfn: (
      previousValue: any,
      currentValue: any,
      currentIndex: number,
      array: any,
    ) => any,
    initialValue?: any,
  ): any;
  reduce(...args: any[]) {
    // @ts-ignore
    return Array.prototype.reduce.apply(this, args);
  }
  /**
   * See :js:meth:`Array.reduceRight`. Applies a function against an accumulator
   * and each value of the Sequence (from right to left) to reduce it to a
   * single value.
   * @param callbackfn A function to execute for each element in the Sequence.
   * Its return value is discarded.
   */
  reduceRight(
    callbackfn: (
      previousValue: any,
      currentValue: any,
      currentIndex: number,
      array: any,
    ) => any,
    initialValue: any,
  ): any;
  reduceRight(...args: any[]) {
    // @ts-ignore
    return Array.prototype.reduceRight.apply(this, args);
  }
  /**
   * See :js:meth:`Array.at`. Takes an integer value and returns the item at
   * that index.
   * @param index Zero-based index of the Sequence element to be returned,
   * converted to an integer. Negative index counts back from the end of the
   * Sequence.
   * @returns The element in the Sequence matching the given index.
   */
  at(index: number) {
    return Array.prototype.at.call(this, index);
  }
  /**
   * The :js:meth:`Array.concat` method is used to merge two or more arrays.
   * This method does not change the existing arrays, but instead returns a new
   * array.
   * @param rest Arrays and/or values to concatenate into a new array.
   * @returns A new Array instance.
   */
  concat(...rest: ConcatArray<any>[]) {
    return Array.prototype.concat.apply(this, rest);
  }
  /**
   * The  :js:meth:`Array.includes` method determines whether a Sequence
   * includes a certain value among its entries, returning true or false as
   * appropriate.
   * @param elt
   * @returns
   */
  includes(elt: any) {
    // @ts-ignore
    return this.has(elt);
  }
  /**
   * The :js:meth:`Array.entries` method returns a new iterator object that
   * contains the key/value pairs for each index in the ``Sequence``.
   * @returns A new iterator object.
   */
  entries() {
    return Array.prototype.entries.call(this);
  }
  /**
   * The :js:meth:`Array.keys` method returns a new iterator object that
   * contains the keys for each index in the ``Sequence``.
   * @returns A new iterator object.
   */
  keys() {
    return Array.prototype.keys.call(this);
  }
  /**
   * The :js:meth:`Array.values` method returns a new iterator object that
   * contains the values for each index in the ``Sequence``.
   * @returns A new iterator object.
   */
  values() {
    return Array.prototype.values.call(this);
  }
  /**
   * The :js:meth:`Array.find` method returns the first element in the provided
   * array that satisfies the provided testing function.
   * @param predicate A function to execute for each element in the
   * ``Sequence``. It should return a truthy value to indicate a matching
   * element has been found, and a falsy value otherwise.
   * @param thisArg A value to use as ``this`` when executing ``predicate``.
   * @returns The first element in the ``Sequence`` that satisfies the provided
   * testing function.
   */
  find(
    predicate: (value: any, index: number, obj: any[]) => any,
    thisArg?: any,
  ) {
    return Array.prototype.find.call(this, predicate, thisArg);
  }
  /**
   * The :js:meth:`Array.findIndex` method returns the index of the first
   * element in the provided array that satisfies the provided testing function.
   * @param predicate A function to execute for each element in the
   * ``Sequence``. It should return a truthy value to indicate a matching
   * element has been found, and a falsy value otherwise.
   * @param thisArg A value to use as ``this`` when executing ``predicate``.
   * @returns The index of the first element in the ``Sequence`` that satisfies
   * the provided testing function.
   */
  findIndex(
    predicate: (value: any, index: number, obj: any[]) => any,
    thisArg?: any,
  ): number {
    return Array.prototype.findIndex.call(this, predicate, thisArg);
  }

  toJSON(this: any) {
    return Array.from(this);
  }

  /**
   * Returns the object treated as a json adaptor.
   *
   * With a JsonAdaptor:
   *  1. property access / modification / deletion is implemented with
   *     :meth:`~object.__getitem__`, :meth:`~object.__setitem__`, and
   *     :meth:`~object.__delitem__` respectively.
   *  2. If an attribute is accessed and the result implements
   *     :meth:`~object.__getitem__` then the result will also be a json
   *     adaptor.
   *
   * For instance, ``JSON.stringify(proxy.asJsJson())`` acts like an
   * inverse to Python's :py:func:`json.loads`.
   */
  asJsJson(): PyProxy & {} {
    // This is just here for the docs. The actual implementation comes from
    // PyAsJsonAdaptorMethods.
    throw new Error("Should not happen");
  }
}

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is an
 * :py:class:`~collections.abc.MutableSequence` (i.e., a :py:class:`list`)
 */
export class PyMutableSequence extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_SEQUENCE);
  }
}

export interface PyMutableSequence extends PyMutableSequenceMethods {}

export class PyMutableSequenceMethods {
  /**
   * The :js:meth:`Array.reverse` method reverses a :js:class:`PyMutableSequence` in
   * place.
   * @returns A reference to the same :js:class:`PyMutableSequence`
   */
  reverse(): PyMutableSequence {
    // @ts-ignore
    this.$reverse();
    // @ts-ignore
    return this;
  }
  /**
   * The :js:meth:`Array.sort` method sorts the elements of a
   * :js:class:`PyMutableSequence` in place.
   * @param compareFn A function that defines the sort order.
   * @returns A reference to the same :js:class:`PyMutableSequence`
   */
  sort(compareFn?: (a: any, b: any) => number): PyMutableSequence {
    // Copy the behavior of sort described here:
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/sort#creating_displaying_and_sorting_an_array
    // Yes JS sort is weird.

    // We need this adaptor to convert from js comparison function to Python key
    // function.
    const functools = API.public_api.pyimport("functools");
    const cmp_to_key = functools.cmp_to_key;
    let cf: (a: any, b: any) => number;
    if (compareFn) {
      cf = compareFn;
    } else {
      cf = defaultCompareFunc;
    }
    // spec says arguments to compareFunc "Will never be undefined."
    // and undefined values should get sorted to end of list.
    // Make wrapper to ensure this
    function wrapper(a: any, b: any) {
      if (a === undefined && b === undefined) {
        return 0;
      }
      if (a === undefined) {
        return 1;
      }
      if (b === undefined) {
        return -1;
      }
      return cf(a, b);
    }
    let key;
    try {
      key = cmp_to_key(wrapper);
      // @ts-ignore
      this.$sort.callKwargs({ key });
    } finally {
      key?.destroy();
      cmp_to_key.destroy();
      functools.destroy();
    }
    // @ts-ignore
    return this;
  }
  /**
   * The :js:meth:`Array.splice` method changes the contents of a
   * :js:class:`PyMutableSequence` by removing or replacing existing elements and/or
   * adding new elements in place.
   * @param start Zero-based index at which to start changing the
   * :js:class:`PyMutableSequence`.
   * @param deleteCount An integer indicating the number of elements in the
   * :js:class:`PyMutableSequence` to remove from ``start``.
   * @param items The elements to add to the :js:class:`PyMutableSequence`, beginning from
   * ``start``.
   * @returns An array containing the deleted elements.
   */
  splice(start: number, deleteCount?: number, ...items: any[]) {
    if (deleteCount === undefined) {
      // Max ssize
      deleteCount = 1 << (31 - 1);
    }
    return python_slice_assign(this, start, start + deleteCount, items);
  }
  /**
   * The :js:meth:`Array.push` method adds the specified elements to the end of
   * a :js:class:`PyMutableSequence`.
   * @param elts The element(s) to add to the end of the :js:class:`PyMutableSequence`.
   * @returns The new length property of the object upon which the method was
   * called.
   */
  push(...elts: any[]) {
    for (let elt of elts) {
      // @ts-ignore
      this.append(elt);
    }
    // @ts-ignore
    return this.length;
  }
  /**
   * The :js:meth:`Array.pop` method removes the last element from a
   * :js:class:`PyMutableSequence`.
   * @returns The removed element from the :js:class:`PyMutableSequence`; undefined if the
   * :js:class:`PyMutableSequence` is empty.
   */
  pop() {
    return python_pop(this, false);
  }
  /**
   * The :js:meth:`Array.shift` method removes the first element from a
   * :js:class:`PyMutableSequence`.
   * @returns The removed element from the :js:class:`PyMutableSequence`; undefined if the
   * :js:class:`PyMutableSequence` is empty.
   */
  shift() {
    return python_pop(this, true);
  }
  /**
   * The :js:meth:`Array.unshift` method adds the specified elements to the
   * beginning of a :js:class:`PyMutableSequence`.
   * @param elts The elements to add to the front of the :js:class:`PyMutableSequence`.
   * @returns The new length of the :js:class:`PyMutableSequence`.
   */
  unshift(...elts: any[]) {
    elts.forEach((elt, idx) => {
      // @ts-ignore
      this.insert(idx, elt);
    });
    // @ts-ignore
    return this.length;
  }
  /**
   * The :js:meth:`Array.copyWithin` method shallow copies part of a
   * :js:class:`PyMutableSequence` to another location in the same :js:class:`PyMutableSequence`
   * without modifying its length.
   * @param target Zero-based index at which to copy the sequence to.
   * @param start Zero-based index at which to start copying elements from.
   * @param end Zero-based index at which to end copying elements from.
   * @returns The modified :js:class:`PyMutableSequence`.
   */
  copyWithin(target: number, start?: number, end?: number): any;
  copyWithin(...args: number[]): any {
    // @ts-ignore
    Array.prototype.copyWithin.apply(this, args);
    return this;
  }
  /**
   * The :js:meth:`Array.fill` method changes all elements in an array to a
   * static value, from a start index to an end index.
   * @param value Value to fill the array with.
   * @param start Zero-based index at which to start filling. Default 0.
   * @param end Zero-based index at which to end filling. Default
   * ``list.length``.
   * @returns
   */
  fill(value: any, start?: number, end?: number): any;
  fill(...args: any[]): any {
    // @ts-ignore
    Array.prototype.fill.apply(this, args);
    return this;
  }
}

// Another layer of boilerplate. The PyProxyHandlers have some annoying logic to
// deal with straining out the spurious "Function" properties "prototype",
// "arguments", and "length", to deal with correctly satisfying the Proxy
// invariants, and to deal with the mro
function python_hasattr(jsobj: PyProxy, jskey: any) {
  let ptrobj = _getPtr(jsobj);
  let result;
  try {
    Py_ENTER();
    result = __pyproxy_hasattr(ptrobj, jskey);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (result === -1) {
    _pythonexc2js();
  }
  return result !== 0;
}

// Returns a JsRef in order to allow us to differentiate between "not found"
// (in which case we return 0) and "found 'None'" (in which case we return
// undefined).
function python_getattr(jsobj: PyProxy, key: any) {
  const { shared } = _getAttrs(jsobj);
  let cache = shared.cache.map;
  let result;
  try {
    Py_ENTER();
    result = __pyproxy_getattr(shared.ptr, key, cache);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (result === null) {
    if (_PyErr_Occurred()) {
      _pythonexc2js();
    }
    return undefined;
  }
  return result;
}

function python_setattr(jsobj: PyProxy, jskey: any, jsval: any) {
  let ptrobj = _getPtr(jsobj);
  let err;
  try {
    Py_ENTER();
    err = __pyproxy_setattr(ptrobj, jskey, jsval);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (err === -1) {
    _pythonexc2js();
  }
}

function python_delattr(jsobj: PyProxy, jskey: any) {
  let ptrobj = _getPtr(jsobj);
  let err;
  try {
    Py_ENTER();
    err = __pyproxy_delattr(ptrobj, jskey);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (err === -1) {
    _pythonexc2js();
  }
}

function python_slice_assign(
  jsobj: any,
  start: number,
  stop: number,
  val: any,
): any[] {
  let ptrobj = _getPtr(jsobj);
  let res;
  try {
    Py_ENTER();
    res = __pyproxy_slice_assign(ptrobj, start, stop, val);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (res === null) {
    _pythonexc2js();
  }
  return res;
}

function python_pop(jsobj: any, pop_start: boolean): any {
  let ptrobj = _getPtr(jsobj);
  let res;
  try {
    Py_ENTER();
    res = __pyproxy_pop(ptrobj, pop_start);
    Py_EXIT();
  } catch (e) {
    API.fatal_error(e);
  }
  if (res === null) {
    _pythonexc2js();
  }
  return res;
}

function filteredHasKey(
  jsobj: PyProxy,
  jskey: string | symbol,
  filterProto: boolean,
) {
  if (jsobj instanceof Function) {
    // If we are a PyProxy of a callable we have to subclass function so that if
    // someone feature detects callables with `instanceof Function` it works
    // correctly. But the callable might have attributes `name` and `length` and
    // we don't want to shadow them with the values from `Function.prototype`.
    return (
      jskey in jsobj &&
      !(
        [
          "name",
          "length",
          "caller",
          "arguments",
          // we are required by JS law to return `true` for `"prototype" in pycallable`
          // but we are allowed to return the value of `getattr(pycallable, "prototype")`.
          // So we filter prototype out of the "get" trap but not out of the "has" trap
          filterProto ? "prototype" : undefined,
        ] as (string | symbol)[]
      ).includes(jskey)
    );
  } else {
    return jskey in jsobj;
  }
}

// See explanation of which methods should be defined here and what they do
// here:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy
const PyProxyHandlers = {
  isExtensible(): boolean {
    return true;
  },
  has(jsobj: PyProxy, jskey: string | symbol): boolean {
    // Note: must report "prototype" in proxy when we are callable.
    // (We can return the wrong value from "get" handler though.)
    if (filteredHasKey(jsobj, jskey, false)) {
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
  get(jsobj: PyProxy, jskey: string | symbol): any {
    // Preference order:
    // 1. stuff from JavaScript
    // 2. the result of Python getattr
    // python_getattr will crash if given a Symbol.
    if (typeof jskey === "symbol" || filteredHasKey(jsobj, jskey, true)) {
      return Reflect.get(jsobj, jskey);
    }
    // If keys start with $ remove the $. User can use initial $ to
    // unambiguously ask for a key on the Python object.
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    // 2. The result of getattr
    return python_getattr(jsobj, jskey);
  },
  set(jsobj: PyProxy, jskey: string | symbol, jsval: any): boolean {
    let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
    if (descr && !descr.writable && !descr.set) {
      return false;
    }
    // python_setattr will crash if given a Symbol.
    if (typeof jskey === "symbol" || filteredHasKey(jsobj, jskey, true)) {
      return Reflect.set(jsobj, jskey, jsval);
    }
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    python_setattr(jsobj, jskey, jsval);
    return true;
  },
  deleteProperty(jsobj: PyProxy, jskey: string | symbol): boolean {
    let descr = Object.getOwnPropertyDescriptor(jsobj, jskey);
    if (descr && !descr.configurable) {
      // Must return "false" if "jskey" is a nonconfigurable own property.
      // Otherwise JavaScript will throw a TypeError.
      // Strict mode JS will throw an error here saying that the property cannot
      // be deleted. It's good to leave everything alone so that the behavior is
      // consistent with the error message.
      return false;
    }
    if (typeof jskey === "symbol" || filteredHasKey(jsobj, jskey, true)) {
      return Reflect.deleteProperty(jsobj, jskey);
    }
    if (jskey.startsWith("$")) {
      jskey = jskey.slice(1);
    }
    python_delattr(jsobj, jskey);
    return true;
  },
  ownKeys(jsobj: PyProxy): (string | symbol)[] {
    let ptrobj = _getPtr(jsobj);
    let result;
    try {
      Py_ENTER();
      result = __pyproxy_ownKeys(ptrobj);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }
    result.push(...Reflect.ownKeys(jsobj));
    return result;
  },
  apply(jsobj: PyProxy & Function, jsthis: any, jsargs: any): any {
    return jsobj.apply(jsthis, jsargs);
  },
};

function isPythonError(e: any): boolean {
  return (
    e &&
    typeof e === "object" &&
    e.constructor &&
    e.constructor.name === "PythonError"
  );
}
const PyProxySequenceHandlers = {
  isExtensible(): boolean {
    return true;
  },
  has(jsobj: PyProxy, jskey: any): boolean {
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      return Number(jskey) < jsobj.length;
    }
    return PyProxyHandlers.has(jsobj, jskey);
  },
  get(jsobj: PyProxy, jskey: any): any {
    if (jskey === "length") {
      return jsobj.length;
    }
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      try {
        return PyGetItemMethods.prototype.get.call(jsobj, Number(jskey));
      } catch (e) {
        if (isPythonError(e)) {
          return undefined;
        }
        throw e;
      }
    }
    return PyProxyHandlers.get(jsobj, jskey);
  },
  set(jsobj: PyProxy, jskey: any, jsval: any): boolean {
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      try {
        PySetItemMethods.prototype.set.call(jsobj, Number(jskey), jsval);
        return true;
      } catch (e) {
        if (isPythonError(e)) {
          return false;
        }
        throw e;
      }
    }
    return PyProxyHandlers.set(jsobj, jskey, jsval);
  },
  deleteProperty(jsobj: PyProxy, jskey: any): boolean {
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      try {
        PySetItemMethods.prototype.delete.call(jsobj, Number(jskey));
        return true;
      } catch (e) {
        if (isPythonError(e)) {
          return false;
        }
        throw e;
      }
    }
    return PyProxyHandlers.deleteProperty(jsobj, jskey);
  },
  ownKeys(jsobj: PyProxy): (string | symbol)[] {
    const result = PyProxyHandlers.ownKeys(jsobj);
    result.push(
      ...Array.from({ length: jsobj.length }, (_, k) => k.toString()),
    );
    result.push("length");
    return result;
  },
};

const PyProxyJsonAdaptorDictHandlers = {
  isExtensible(): boolean {
    return true;
  },
  has(jsobj: PyProxy, jskey: any): boolean {
    if (PyContainsMethods.prototype.has.call(jsobj, jskey)) {
      return true;
    }
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      jskey = Number(jskey);
    }
    if (PyContainsMethods.prototype.has.call(jsobj, jskey)) {
      return true;
    }
    return false;
  },
  get(jsobj: PyProxy, jskey: any): any {
    let result;
    if (
      ["copy", "constructor", "$$flags", "toString", "destroy"].includes(
        jskey,
      ) ||
      typeof jskey === "symbol"
    ) {
      // @ts-ignore
      return Reflect.get(...arguments);
    }
    if (typeof jskey === "string") {
      // TODO: consider adding an attribute cache for asJsJson
      result = PyGetItemMethods.prototype.get.call(jsobj, jskey);
    }
    if (result) {
      return result;
    }
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      jskey = Number(jskey);
      result = PyGetItemMethods.prototype.get.call(jsobj, jskey);
    }
    if (result) {
      return result;
    }
    // @ts-ignore
    return Reflect.get(...arguments);
  },
  set(jsobj: PyProxy, jskey: any, jsval: any): boolean {
    if (typeof jskey === "string") {
      if (/^[0-9]+$/.test(jskey)) {
        jskey = Number(jskey);
      }
      try {
        PySetItemMethods.prototype.set.call(jsobj, jskey, jsval);
        return true;
      } catch (e) {
        if (isPythonError(e)) {
          return false;
        }
        throw e;
      }
    }
    return false;
  },
  deleteProperty(jsobj: PyProxy, jskey: any): boolean {
    if (typeof jskey === "string" && /^[0-9]+$/.test(jskey)) {
      try {
        PySetItemMethods.prototype.delete.call(jsobj, Number(jskey));
        return true;
      } catch (e) {
        if (isPythonError(e)) {
          return false;
        }
        throw e;
      }
    }
    return false;
  },
  getOwnPropertyDescriptor(jsobj: PyProxy, prop: any) {
    if (!PyProxyJsonAdaptorDictHandlers.has(jsobj, prop)) {
      return undefined;
    }
    const value = PyProxyJsonAdaptorDictHandlers.get(jsobj, prop);
    return {
      configurable: true,
      enumerable: true,
      value,
      writable: true,
    };
  },
  ownKeys(jsobj: PyProxy): (string | symbol)[] {
    let dict_keys_view: Iterable<string> & PyProxy;
    dict_keys_view = PyProxyHandlers.get(jsobj, "keys")();
    const res = Array.from(dict_keys_view);
    dict_keys_view.destroy();
    return res;
  },
};

/**
 * A :js:class:`~pyodide.ffi.PyProxy` whose proxied Python object is :ref:`awaitable
 * <asyncio-awaitables>` (i.e., has an :meth:`~object.__await__` method).
 */
export class PyAwaitable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyProxy {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_AWAITABLE);
  }
}

export interface PyAwaitable extends Promise<any> {}

/**
 * The Promise / JavaScript awaitable API.
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
    const { shared } = _getAttrsQuiet(this);
    if (shared.promise) {
      return shared.promise;
    }
    const ptr = shared.ptr;
    if (!ptr) {
      // Destroyed and promise wasn't resolved. Raise error!
      _getAttrs(this);
    }
    let resolveHandle: (v: any) => void;
    let rejectHandle: (e: any) => void;
    let promise = new Promise((resolve, reject) => {
      resolveHandle = resolve;
      rejectHandle = reject;
    });
    let err;
    try {
      Py_ENTER();
      err = __pyproxy_ensure_future(ptr, resolveHandle!, rejectHandle!);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (err === -1) {
      _pythonexc2js();
    }
    shared.promise = promise;
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
 * :std:term:`callable` (i.e., has an :py:meth:`~object.__call__` method).
 */
export class PyCallable extends PyProxy {
  /** @private */
  static [Symbol.hasInstance](obj: any): obj is PyCallable {
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_CALLABLE);
  }
}

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
   * Call the Python function. The first parameter controls various parameters
   * that change the way the call is performed.
   *
   * @param options
   * @param options.kwargs If true, the last argument is treated as a collection
   *                       of keyword arguments.
   * @param options.promising If true, the call is made with stack switching
   *                          enabled. Not needed if the callee is an async
   *                          Python function.
   * @param options.relaxed If true, extra arguments are ignored instead of
   *                        raising a :py:exc:`TypeError`.
   * @param jsargs Arguments to the Python function.
   * @returns
   */
  callWithOptions(
    {
      relaxed,
      kwargs,
      promising,
    }: { relaxed?: boolean; kwargs?: boolean; promising?: boolean },
    ...jsargs: any
  ) {
    let kwarg = {};
    if (kwargs) {
      if (jsargs.length === 0) {
        throw new TypeError(
          "callWithOptions with 'kwargs: true' requires at least one argument (the key word argument object)",
        );
      }
      kwarg = jsargs.pop();
      if (
        kwarg.constructor !== undefined &&
        kwarg.constructor.name !== "Object"
      ) {
        throw new TypeError("kwargs argument is not an object");
      }
    }
    const target = relaxed ? API.pyodide_code.relaxed_call : this;
    if (relaxed) {
      jsargs.unshift(this);
    }
    const callFunc = promising
      ? callPyObjectKwargsPromising
      : callPyObjectKwargs;
    return callFunc(_getPtr(target), jsargs, kwarg);
  }

  /**
   * Call the function with keyword arguments. The last argument must be an
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
    return callPyObjectKwargs(_getPtr(this), jsargs, kwargs);
  }

  /**
   * Call the function in a "relaxed" manner. Any extra arguments will be
   * ignored. This matches the behavior of JavaScript functions more accurately.
   *
   * Any extra arguments will be ignored. This matches the behavior of
   * JavaScript functions more accurately. Missing arguments are **NOT** filled
   * with `None`. If too few arguments are passed, this will still raise a
   * TypeError.
   *
   * This uses :py:func:`pyodide.code.relaxed_call`.
   */
  callRelaxed(...jsargs: any) {
    return API.pyodide_code.relaxed_call(this, ...jsargs);
  }

  /**
   * Call the function with keyword arguments in a "relaxed" manner. The last
   * argument must be an object with the keyword arguments. Any extra arguments
   * will be ignored. This matches the behavior of JavaScript functions more
   * accurately.
   *
   * Missing arguments are **NOT** filled with ``None``. If too few arguments are
   * passed, this will still raise a :py:exc:`TypeError`. Also, if the same argument is
   * passed as both a keyword argument and a positional argument, it will raise
   * an error.
   *
   * This uses :py:func:`pyodide.code.relaxed_call`.
   */
  callKwargsRelaxed(...jsargs: any) {
    return API.pyodide_code.relaxed_call.callKwargs(this, ...jsargs);
  }

  /**
   * Call the function with stack switching enabled. The last argument must be
   * an object with the keyword arguments. Functions called this way can use
   * :py:meth:`~pyodide.ffi.run_sync` to block until an
   * :py:class:`~collections.abc.Awaitable` is resolved. Only works in runtimes
   * with JS Promise integration.
   *
   * .. admonition:: Experimental
   *    :class: warning
   *
   *    This feature is not yet stable.
   *
   * @experimental
   */
  callPromising(...jsargs: any) {
    return callPyObjectKwargsPromising(_getPtr(this), jsargs, {});
  }

  /**
   * Call the function with stack switching enabled. The last argument must be
   * an object with the keyword arguments. Functions called this way can use
   * :py:meth:`~pyodide.ffi.run_sync` to block until an
   * :py:class:`~collections.abc.Awaitable` is resolved. Only works in runtimes
   * with JS Promise integration.
   *
   * .. admonition:: Experimental
   *    :class: warning
   *
   *    This feature is not yet stable.
   *
   * @experimental
   */
  callPromisingKwargs(...jsargs: any) {
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
    return callPyObjectKwargsPromising(_getPtr(this), jsargs, kwargs);
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
    let { shared, props } = _getAttrs(this);
    const { boundArgs: boundArgsOld, boundThis: boundThisOld, isBound } = props;
    let boundThis = thisArg;
    if (isBound) {
      boundThis = boundThisOld;
    }
    let boundArgs = boundArgsOld.concat(jsargs);
    props = Object.assign({}, props, {
      boundArgs,
      isBound: true,
      boundThis,
    });
    return pyproxy_new(shared.ptr, {
      shared,
      flags: _getFlags(this),
      props,
    });
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
    let { props, shared } = _getAttrs(this);
    props = Object.assign({}, props, {
      captureThis: true,
    });
    return pyproxy_new(shared.ptr, {
      shared,
      flags: _getFlags(this),
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
    return API.isPyProxy(obj) && !!(_getFlags(obj) & IS_BUFFER);
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
   * ``"i64"``, ``"u64"``, ``"f32"``, ``"f64"``, or ``"dataview"``. This argument
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
    let this_ptr = _getPtr(this);
    let result;
    try {
      Py_ENTER();
      result = __pyproxy_get_buffer(this_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    if (result === null) {
      _pythonexc2js();
    }

    const {
      start_ptr,
      smallest_ptr,
      largest_ptr,
      readonly,
      format,
      itemsize,
      shape,
      strides,
      view,
      c_contiguous,
      f_contiguous,
    } = result;

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
      let numBytes = largest_ptr - smallest_ptr;
      if (
        numBytes !== 0 &&
        (start_ptr % alignment !== 0 ||
          smallest_ptr % alignment !== 0 ||
          largest_ptr % alignment !== 0)
      ) {
        throw new Error(
          `Buffer does not have valid alignment for a ${ArrayType.name}`,
        );
      }
      let numEntries = numBytes / alignment;
      let offset = (start_ptr - smallest_ptr) / alignment;
      let data;
      if (numBytes === 0) {
        data = new ArrayType();
      } else {
        data = new ArrayType(HEAPU32.buffer, smallest_ptr, numEntries);
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
          _view_ptr: view,
          _released: false,
        }),
      );
      // Module.bufferFinalizationRegistry.register(result, view_ptr, result);
      return result;
    } finally {
      if (!success) {
        try {
          Py_ENTER();
          _PyBuffer_Release(view);
          _PyMem_Free(view);
          Py_EXIT();
        } catch (e) {
          API.fatal_error(e);
        }
      }
    }
  }
}

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
 *     function multiIndexToIndex(pybuff, multiIndex) {
 *       if (multindex.length !== pybuff.ndim) {
 *         throw new Error("Wrong length index");
 *       }
 *       let idx = pybuff.offset;
 *       for (let i = 0; i < pybuff.ndim; i++) {
 *         if (multiIndex[i] < 0) {
 *           multiIndex[i] = pybuff.shape[i] - multiIndex[i];
 *         }
 *         if (multiIndex[i] < 0 || multiIndex[i] >= pybuff.shape[i]) {
 *           throw new Error("Index out of range");
 *         }
 *         idx += multiIndex[i] * pybuff.stride[i];
 *       }
 *       return idx;
 *     }
 *     console.log("entry is", pybuff.data[multiIndexToIndex(pybuff, [2, 0, -1])]);
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
   * :js:attr:`buff.data.byteLength <TypedArray.byteLength>`. See
   * :py:attr:`memoryview.nbytes`.
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

  /**
   * @private
   */
  _released: boolean;
  /**
   * @private
   */
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
      _PyBuffer_Release(this._view_ptr);
      _PyMem_Free(this._view_ptr);
      Py_EXIT();
    } catch (e) {
      API.fatal_error(e);
    }
    this._released = true;
    // @ts-ignore
    this.data = null;
  }
}
