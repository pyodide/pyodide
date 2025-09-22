export {};
import type { PyProxy, PyAwaitable } from "generated/pyproxy";
import { type PyodideAPI } from "./api";
import { type ConfigType } from "./pyodide";
import { type InFuncType } from "./streams";
import { SnapshotConfig } from "./snapshot";
import { ResolvablePromise } from "./common/resolveable";
import { PackageManager } from "./load-package";
/**
 * @docgroup pyodide.ffi
 */
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

declare global {
  export var Module: PyodideModule;
  export var API: API;
}

// Emscripten runtime methods

// These should be declared with EM_JS_DEPS so that when linking libpyodide it's
// not necessary to put them in `-s EXPORTED_RUNTIME_METHODS`.
declare global {
  export const stringToNewUTF8: (str: string) => number;
  // export const UTF8ToString: (ptr: number) => string; => removed due to duplicate with @types/emscripten
  export const UTF8ArrayToString: (buf: Uint8Array) => string;
  // export const stackAlloc: (sz: number) => number; => removed due to duplicate with @types/emscripten
  // export const stackSave: () => number; => removed due to duplicate with @types/emscripten
  // export const stackRestore: (ptr: number) => void; => removed due to duplicate with @types/emscripten
  export const HEAPU32: Uint32Array;
}

// Library functions that are used in JS. To link with dce, these all need to be
// passed to -sEXPORTED_FUNCTIONS.
// TODO: Figure out how to avoid needing to do this.
declare global {
  // also need:
  // _hiwire_new, _hiwire_intern, _hiwire_num_refs, _hiwire_get,
  // _hiwire_incref, _hiwire_decref, and _hiwire_pop
  //
  // _PyUnicode_New,
  // __PyLong_FromByteArray, _PyLong_FromDouble, _PyFloat_FromDouble,
  // _PyList_New, _PyDict_New, _PyDict_SetItem, _PySet_New, _PySet_Add
  // _PyEval_SaveThread, _PyEval_RestoreThread,
  //   _PyErr_CheckSignals, _PyErr_SetString
  export const _free: (a: number) => void;
  export const __PyTraceback_Add: (a: number, b: number, c: number) => void;
  export const _PyRun_SimpleString: (ptr: number) => number;
  export const _PyErr_Occurred: () => number;
  export const _PyErr_Print: () => void;
  export const _Py_IncRef: (ptr: number) => void;
  export const _Py_DecRef: (ptr: number) => void;
  export const _PyObject_GetIter: (ptr: number) => number;
  export const _PyObject_GetAIter: (ptr: number) => number;
  export const _PyObject_Size: (ptr: number) => number;
  export const _PyBuffer_Release: (ptr: number) => number;
  export const _PyMem_Free: (ptr: number) => number;
  export const _PyGILState_Check: () => number;
  export const __PyErr_CheckSignals: () => number;
  export const _PyErr_SetRaisedException: (ptr: number) => void;
}

// Our own functions we use from JavaScript. These all need to be labeled with
// EMSCRIPTEN_KEEPALIVE
declare global {
  // also: _JsString_FromId, _wrap_exception, _PyUnicode_Data, __js2python_none,
  // __js2python_true, __js2python_false, __js2python_pyproxy, _JsBuffer_CopyIntoMemoryView
  export const _check_gil: () => void;
  export const _dump_traceback: () => void;
  export const _pythonexc2js: () => void;
  export const _restore_sys_last_exception: (err: number) => boolean;
  export const _set_error: (pyerr: number) => void;

  export const _JsProxy_create: (obj: any) => number;
  export const _JsProxy_Check: (ptr: number) => number;

  export const _python2js: (pyobj: number) => any;
  export const _python2js_custom: (
    obj: number,
    depth: number,
    proxies: PyProxy[] | null,
    dict_converter:
      | null
      | ((array: Iterable<[key: string, value: any]>) => any),
    default_converter:
      | null
      | ((
          obj: PyProxy,
          convert: (obj: PyProxy) => any,
          cacheConversion: (obj: PyProxy, result: any) => void,
        ) => any),
    eager_converter:
      | null
      | ((
          obj: PyProxy,
          convert: (obj: PyProxy) => any,
          cacheConversion: (obj: PyProxy, result: any) => void,
        ) => any),
  ) => any;

  export const _pyproxy_getflags: (
    ptr: number,
    is_json_adaptor: boolean,
  ) => number;
  export const __pyproxy_type: (ptr: number) => string;
  export const __pyproxy_repr: (ptr: number) => string;
  export const __pyproxy_getitem: (
    obj: number,
    key: any,
    cache: Map<string, any>,
    is_json_adaptor: boolean,
  ) => any;
  export const __pyproxy_setitem: (ptr: number, key: any, value: any) => number;
  export const __pyproxy_delitem: (ptr: number, key: any) => number;
  export const __pyproxy_contains: (ptr: number, key: any) => number;
  export const __pyproxy_GetIter: (ptr: number) => number;
  export const __pyproxy_GetAIter: (ptr: number) => number;
  export const __pyproxy_aiter_next: (ptr: number) => any;
  export const __pyproxy_iter_next: (
    ptr: number,
    cache: Map<string, any>,
    is_json_adaptor: boolean,
  ) => any;
  export const __pyproxyGen_Send: (
    ptr: number,
    arg: any,
  ) => IteratorResult<any>;
  export const __pyproxyGen_return: (
    ptr: number,
    arg: any,
  ) => IteratorResult<any>;
  export const __pyproxyGen_throw: (
    ptr: number,
    arg: any,
  ) => IteratorResult<any>;
  export const __pyproxyGen_asend: (ptr: number, idarg: number) => PyAwaitable;
  export const __pyproxyGen_areturn: (ptr: number) => PyAwaitable;
  export const __pyproxyGen_athrow: (ptr: number, idarg: number) => PyAwaitable;
  export const __pyproxy_getattr: (
    ptr: number,
    attr: string,
    cache: Map<string, any>,
  ) => any;
  export const __pyproxy_setattr: (
    ptr: number,
    attr: string,
    value: any,
  ) => number;
  export const __pyproxy_delattr: (ptr: number, attr: string) => number;
  export const __pyproxy_hasattr: (ptr: number, attr: string) => number;
  export const __pyproxy_slice_assign: (
    ptr: number,
    start: number,
    stop: number,
    val: number,
  ) => any[];
  export const __pyproxy_pop: (ptr: number, popstart: boolean) => any;
  export const __pyproxy_ownKeys: (ptr: number) => (string | symbol)[];
  export const __pyproxy_ensure_future: (
    ptr: number,
    resolve: (res: any) => void,
    reject: (exc: any) => void,
  ) => number;
  export const __pyproxy_get_buffer: (this_: number) => any;
  export const __pyproxy_apply: (
    ptr: number,
    jsargs: any[],
    num_pos_args: number,
    kwargs_names: string[],
    num_kwargs: number,
  ) => any;
  export const __iscoroutinefunction: (a: number) => number;
}

/** @hidden */
export type FSNode = {
  timestamp: number;
  rdev: number;
  contents: Uint8Array;
  mode: number;
};

/** @hidden */
export type FSStream = {
  tty?: {
    ops: object;
  };
  seekable?: boolean;
  stream_ops: FSStreamOps;
  node: FSNode;
};

/** @hidden */
export type FSStreamOps = FSStreamOpsGen<FSStream>;

/** @hidden */
export type FSStreamOpsGen<T> = {
  open: (a: T) => void;
  close: (a: T) => void;
  fsync: (a: T) => void;
  read: (
    a: T,
    b: Uint8Array,
    offset: number,
    length: number,
    pos: number,
  ) => number;
  write: (
    a: T,
    b: Uint8Array,
    offset: number,
    length: number,
    pos: number,
  ) => number;
};

/**
 * Methods that the Emscripten filesystem provides. Most of them are already defined
 * in `@types/emscripten`, but Pyodide uses quite a lot of private APIs that are not
 * defined there as well. Hence this interface.
 *
 * TODO: Consider upstreaming these APIs to `@types/emscripten`.
 * @hidden
 */
interface PyodideFSType {
  mkdirTree: (path: string, mode?: number) => void;
  createDevice: ((
    parent: string,
    name: string,
    input?: (() => number | null) | null,
    output?: ((code: number) => void) | null,
  ) => FSNode) & {
    major: number;
  };
  lookupPath: (
    path: string,
    options?: {
      follow_mount?: boolean;
    },
  ) => { node: FSNode };
  open: (path: string, flags: string | number, mode?: number) => FSStream;
  filesystems: any;
  isMountpoint: (node: FSNode) => boolean;
  closeStream: (fd: number) => void;
  registerDevice<T>(dev: number, ops: FSStreamOpsGen<T>): void;
  writeFile: (path: string, contents: any, o?: { canOwn?: boolean }) => void;
}

/**
 * Combined filesystem type that omits the incompatible lookupPath from `@types/emscripten` and adds Pyodide-specific filesystem methods.
 * TODO: Consider upstreaming these APIs to `@types/emscripten`
 * @hidden
 */
export type FSType = Omit<typeof FS, "lookupPath"> & PyodideFSType;

/** @hidden */
export type PreRunFunc = (Module: PyodideModule) => void;

type DSO = any;

/** @hidden */
export interface LDSO {
  loadedLibsByName: {
    [key: string]: DSO;
  };
}

/** @hidden */
export interface EmscriptenModule {
  locateFile: (file: string) => string;
  exited?: { toThrow: any };
  ENV: { [key: string]: string };
  PATH: any;
  TTY: any;
  FS: FSType;
  LDSO: LDSO;
  canvas?: HTMLCanvasElement;
  addRunDependency(id: string): void;
  removeRunDependency(id: string): void;
  getDylinkMetadata(binary: Uint8Array | WebAssembly.Module): {
    neededDynlibs: string[];
  };

  ERRNO_CODES: { [k: string]: number };
  stringToNewUTF8(x: string): number;
  stringToUTF8OnStack: (str: string) => number;
  HEAP8: Uint8Array;
  HEAPU32: Uint32Array;
  getExceptionMessage(e: number): [string, string];
  exitCode: number | undefined;
  ExitStatus: { new (exitCode: number): Error };
  _free: (ptr: number) => void;
  stackSave: () => number;
  stackRestore: (ptr: number) => void;
  promiseMap: {
    free(id: number): void;
  };
  _emscripten_dlopen_promise(lib: number, flags: number): number;
  _dlerror(): number;
  UTF8ToString: (
    ptr: number,
    maxBytesToRead: number,
    ignoreNul?: boolean,
  ) => string;
}

/** @hidden */
export interface PythonModule extends EmscriptenModule {
  _Py_EMSCRIPTEN_SIGNAL_HANDLING: number;
  Py_EmscriptenSignalBuffer: TypedArray;
  _Py_Version: number;
}

/** @hidden */
export interface PyodideModule extends PythonModule {
  API: API;
  _compat_to_string_repr: number;
  _compat_null_to_none: number;
  js2python_convert: (
    obj: any,
    options: {
      depth?: number;
      defaultConverter?: (
        value: any,
        converter: (value: any) => any,
        cacheConversion: (input: any, output: any) => void,
      ) => any;
    },
  ) => any;
  _PropagatePythonError: typeof Error;
  __hiwire_get(a: number): any;
  __hiwire_set(a: number, b: any): void;
  __hiwire_immortal_add(a: any): void;
  _jslib_init(): number;
  _init_pyodide_proxy(): number;

  handle_js_error(e: any): void;
  _print_stdout: (ptr: number) => void;
  _print_stderr: (ptr: number) => void;
  getPromise(p: number): Promise<any>;
}

/**
 * The lockfile platform info. The ``abi_version`` field is used to check if the
 * lockfile is compatible with the interpreter. The remaining fields are
 * informational.
 */
export interface LockfileInfo {
  /**
   * Machine architecture. At present, only can be wasm32. Pyodide has no wasm64
   * build.
   */
  arch: "wasm32";
  /**
   * The ABI version is structured as ``yyyy_patch``. For the lockfile to be
   * compatible with the current interpreter this field must match exactly with
   * the ABI version of the interpreter.
   */
  abi_version: string;
  /**
   * The Emscripten versions for instance, `emscripten_4_0_9`. Different
   * Emscripten versions have different ABIs so if this changes ``abi_version``
   * must also change.
   */
  platform: string;
  /**
   * The Pyodide version the lockfile was made with. Informational only, has no
   * compatibility implications. May be removed in the future.
   */
  version: string;
  /**
   * The Python version this lock file was made with. If the minor version
   * changes (e.g, 3.12 to 3.13) this changes the ABI and the ``abi_version``
   * must change too. Patch versions do not imply a change to the
   * ``abi_version``.
   */
  python: string;
}

/**
 * A package entry in the lock file.
 */
export interface LockfilePackage {
  /**
   * The unnormalized name of the package.
   */
  name: string;
  version: string;
  /**
   * The file name or url of the package wheel. If it's relative, it will be
   * resolved with respect to ``packageBaseUrl``. If there is no
   * ``packageBaseUrl``, attempting to install a package with a relative
   * ``file_name``  will fail.
   */
  file_name: string;
  package_type: PackageType;
  /**
   * The installation directory. Will be ``site`` except for certain system
   * dynamic libraries that need to go on the global LD_LIBRARY_PATH.
   */
  install_dir: "site" | "dynlib";
  /**
   * Integrity. Must be present unless ``checkIntegrity: false`` is passed to
   * ``loadPyodide``.
   */
  sha256: string;
  /**
   * The set of imports provided by this package as best we can tell. Used by
   * :js:func:`pyodide.loadPackagesFromImports` to work out what packages to
   * install.
   */
  imports: string[];
  /**
   * The set of dependencies of this package.
   */
  depends: string[];
}

/**
 * The type of a package lockfile.
 */
export interface Lockfile {
  info: LockfileInfo;
  packages: Record<string, LockfilePackage>;
}

/** @hidden */
export type PackageType =
  | "package"
  | "cpython_module"
  | "shared_library"
  | "static_library";

// Package data inside pyodide-lock.json

export interface PackageData {
  name: string;
  version: string;
  fileName: string;
  /** @experimental */
  packageType: PackageType;
}

/** @hidden */
export type LoadedPackages = Record<string, string>;

/**
 * @hidden
 */
export type PackageLoadMetadata = {
  name: string;
  normalizedName: string;
  channel: string;
  depends: string[];
  done: ResolvablePromise;
  installPromise?: Promise<void>;
  packageData: LockfilePackage;
};

/** @hidden */
export interface API {
  fatal_error: (e: any) => never;
  isPyProxy: (e: any) => e is PyProxy;
  debug_ffi: boolean;
  maybe_fatal_error: (e: any) => void;
  public_api: PyodideAPI;
  config: ConfigType;
  packageIndexReady: Promise<void>;
  bootstrapFinalizedPromise: Promise<void>;
  typedArrayAsUint8Array: (buffer: TypedArray | ArrayBuffer) => Uint8Array;
  initializeStreams: (
    stdin?: InFuncType | undefined,
    stdout?: ((a: string) => void) | undefined,
    stderr?: ((a: string) => void) | undefined,
  ) => void;

  getTypeTag: (o: any) => string;
  inTestHoist?: boolean;
  on_fatal?: (e: any) => void;
  _skip_unwind_fatal_error?: boolean;
  capture_stderr: () => void;
  restore_stderr: () => string;
  fatal_loading_error: (...args: string[]) => never;
  PythonError: any;
  NoGilError: any;
  errorConstructors: Map<string, ErrorConstructor>;
  deserializeError: (name: string, message: string, stack: string) => Error;
  setPyProxyToStringMethod: (useRepr: boolean) => void;
  setCompatNullToNone: (compat: boolean) => void;

  _pyodide: any;
  pyodide_py: any;
  pyodide_code: any;
  pyodide_ffi: any;
  pyodide_base: any;
  globals: PyProxy;
  rawRun: (code: string) => [number, string];
  runPythonInternal: (code: string) => any;
  runPythonInternal_dict: any;
  saveState: () => any;
  restoreState: (state: any) => void;
  scheduleCallback: (callback: () => void, timeout: number) => void;
  detectEnvironment: () => Record<string, boolean>;

  package_loader: any;
  importlib: any;
  _import_name_to_package_name: Map<string, string>;
  lockFilePromise: Promise<Lockfile | string>;
  lockfile_unvendored_stdlibs: string[];
  lockfile_unvendored_stdlibs_and_test: string[];
  lockfile: Lockfile;
  lockfile_info: LockfileInfo;
  lockfile_packages: Record<string, LockfilePackage>;
  packageManager: PackageManager;
  flushPackageManagerBuffers: () => void;
  defaultLdLibraryPath: string[];
  sitepackages: string;
  loadBinaryFile: (
    path: string,
    file_sub_resource_hash?: string | undefined,
  ) => Promise<Uint8Array>;
  loadDynlib: (
    lib: string,
    global: boolean,
    searchDirs?: string[] | undefined,
    readFileFunc?: (path: string) => Uint8Array,
  ) => Promise<void>;
  install: (
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    metadata?: ReadonlyMap<string, string>,
  ) => Promise<void>;
  _Comlink: any;

  dsodir: string;
  sys: PyProxy;
  os: PyProxy;

  restoreSnapshot(snapshot: Uint8Array): SnapshotConfig;
  serializeHiwireState(serializer?: (obj: any) => any): SnapshotConfig;
  makeSnapshot(serializer?: (obj: any) => any): Uint8Array;
  saveSnapshot(): Uint8Array;
  getExpectedKeys(): any[];
  finalizeBootstrap: (
    fromSnapshot?: SnapshotConfig,
    snapshotDeserializer?: (obj: any) => any,
  ) => PyodideAPI;
  syncUpSnapshotLoad3(conf: SnapshotConfig): void;
  abortSignalAny: (signals: AbortSignal[]) => AbortSignal;
  version: string;
  abiVersion: string;
  pyVersionTuple: [number, number, number];
  LiteralMap: any;
  sitePackages: string;
}

// Subset of the API and Module that the package manager needs
/**
 * @hidden
 */
export type PackageManagerAPI = Pick<
  API,
  | "importlib"
  | "package_loader"
  | "lockfile_packages"
  | "bootstrapFinalizedPromise"
  | "sitepackages"
  | "defaultLdLibraryPath"
  | "version"
> & {
  config: Pick<ConfigType, "packageCacheDir" | "packageBaseUrl" | "cdnUrl">;
};
/**
 * @hidden
 */
export type PackageManagerModule = Pick<
  PyodideModule,
  | "PATH"
  | "LDSO"
  | "stringToNewUTF8"
  | "stringToUTF8OnStack"
  | "_print_stderr"
  | "_print_stdout"
  | "stackSave"
  | "stackRestore"
  | "_emscripten_dlopen_promise"
  | "getPromise"
  | "promiseMap"
  | "_dlerror"
  | "UTF8ToString"
>;
