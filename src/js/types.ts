export {};
import type { PyProxy, PyAwaitable } from "generated/pyproxy";
import { type PyodideInterface } from "./api";
import { type ConfigType } from "./pyodide";
import { type InFuncType } from "./streams";
import { SnapshotConfig } from "./snapshot";
import { ResolvablePromise } from "./common/resolveable";

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
  export var Module: Module;
  export var API: API;
}

// Emscripten runtime methods

// These should be declared with EM_JS_DEPS so that when linking libpyodide it's
// not necessary to put them in `-s EXPORTED_RUNTIME_METHODS`.
declare global {
  export const stringToNewUTF8: (str: string) => number;
  export const UTF8ToString: (ptr: number) => string;
  export const FS: FSType;
  export const stackAlloc: (sz: number) => number;
  export const stackSave: () => number;
  export const stackRestore: (ptr: number) => void;
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
  tty?: boolean;
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
 * @hidden
 */
export interface FSType {
  unlink: (path: string) => void;
  mkdirTree: (path: string, mode?: number) => void;
  chdir: (path: string) => void;
  symlink: (target: string, src: string) => FSNode;
  createDevice: ((
    parent: string,
    name: string,
    input?: (() => number | null) | null,
    output?: ((code: number) => void) | null,
  ) => FSNode) & {
    major: number;
  };
  closeStream: (fd: number) => void;
  open: (path: string, flags: string | number, mode?: number) => FSStream;
  makedev: (major: number, minor: number) => number;
  mkdev: (path: string, dev: number) => FSNode;
  filesystems: any;
  stat: (path: string, dontFollow?: boolean) => any;
  readdir: (path: string) => string[];
  isDir: (mode: number) => boolean;
  isMountpoint: (mode: FSNode) => boolean;
  lookupPath: (
    path: string,
    options?: {
      follow_mount?: boolean;
    },
  ) => { node: FSNode };
  isFile: (mode: number) => boolean;
  writeFile: (path: string, contents: any, o?: { canOwn?: boolean }) => void;
  chmod: (path: string, mode: number) => void;
  utime: (path: string, atime: number, mtime: number) => void;
  rmdir: (path: string) => void;
  mount: (type: any, opts: any, mountpoint: string) => any;
  write: (
    stream: FSStream,
    buffer: any,
    offset: number,
    length: number,
    position?: number,
  ) => number;
  close: (stream: FSStream) => void;
  ErrnoError: { new (errno: number): Error };
  registerDevice<T>(dev: number, ops: FSStreamOpsGen<T>): void;
  syncfs(dir: boolean, oncomplete: (val: void) => void): void;
  findObject(a: string, dontResolveLastLink?: boolean): any;
  readFile(a: string): Uint8Array;
}

/** @hidden */
export type PreRunFunc = (Module: Module) => void;

/** @hidden */
export type ReadFileType = (path: string) => Uint8Array;

// File System-like type which can be passed to
// Module.loadDynamicLibrary or Module.loadWebAssemblyModule
/** @hidden */
export type LoadDynlibFS = {
  readFile: ReadFileType;
  findObject: (path: string, dontResolveLastLink: boolean) => any;
};

type DSO = any;

/** @hidden */
export interface LDSO {
  loadedLibsByName: {
    [key: string]: DSO;
  };
}

/**
 * TODO: consider renaming the type to ModuleType to avoid name collisions
 * between Module and ModuleType?
 * @hidden
 */
export interface Module {
  API: API;
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
  reportUndefinedSymbols(): void;
  loadDynamicLibrary(
    lib: string,
    options?: {
      loadAsync?: boolean;
      nodelete?: boolean;
      allowUndefined?: boolean;
      global?: boolean;
      fs: LoadDynlibFS;
    },
    localScope?: object | null,
    handle?: number,
  ): void;
  getDylinkMetadata(binary: Uint8Array | WebAssembly.Module): {
    neededDynlibs: string[];
  };

  ERRNO_CODES: { [k: string]: number };
  stringToNewUTF8(x: string): number;
  _compat_to_string_repr: number;
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
  _Py_EMSCRIPTEN_SIGNAL_HANDLING: number;
  Py_EmscriptenSignalBuffer: TypedArray;
  HEAP8: Uint8Array;
  __hiwire_get(a: number): any;
  __hiwire_set(a: number, b: any): void;
  __hiwire_immortal_add(a: any): void;
  _jslib_init(): number;
  _init_pyodide_proxy(): number;
  jsWrapperTag: any; // Should be WebAssembly.Tag
  getExceptionMessage(e: number): [string, string];
  handle_js_error(e: any): void;
}

type LockfileInfo = {
  arch: "wasm32" | "wasm64";
  platform: string;
  version: string;
  python: string;
};

/** @hidden */
export type Lockfile = {
  info: LockfileInfo;
  packages: Record<string, InternalPackageData>;
};

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
export type InternalPackageData = {
  name: string;
  version: string;
  file_name: string;
  package_type: PackageType;
  install_dir: string;
  sha256: string;
  imports: string[];
  depends: string[];
};

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
  packageData: InternalPackageData;
};

/** @hidden */
export interface API {
  fatal_error: (e: any) => never;
  isPyProxy: (e: any) => e is PyProxy;
  debug_ffi: boolean;
  maybe_fatal_error: (e: any) => void;
  public_api: PyodideInterface;
  config: ConfigType;
  packageIndexReady: Promise<void>;
  bootstrapFinalizedPromise: Promise<void>;
  setCdnUrl: (url: string) => void;
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
  lockFilePromise: Promise<Lockfile>;
  lockfile_unvendored_stdlibs: string[];
  lockfile_unvendored_stdlibs_and_test: string[];
  lockfile_info: LockfileInfo;
  lockfile_packages: Record<string, InternalPackageData>;
  repodata_packages: Record<string, InternalPackageData>;
  repodata_info: LockfileInfo;
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
  // TODO: Remove this from the API after migrating micropip to use the `install` API instead.
  loadDynlibsFromPackage: (
    pkg: { file_name: string },
    dynlibPaths: string[],
  ) => Promise<void>;
  install: (
    buffer: Uint8Array,
    filename: string,
    installDir: string,
    installer: string,
    source: string,
  ) => Promise<void>;
  recursiveDependencies: (
    names: string[],
    errorCallback: (err: string) => void,
  ) => Map<string, PackageLoadMetadata>;
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
  ) => PyodideInterface;
  syncUpSnapshotLoad3(conf: SnapshotConfig): void;
  abortSignalAny: (signals: AbortSignal[]) => AbortSignal;
  version: string;

  LiteralMap: any;
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
> & {
  config: Pick<ConfigType, "indexURL" | "packageCacheDir">;
};
/**
 * @hidden
 */
export type PackageManagerModule = Pick<
  Module,
  "reportUndefinedSymbols" | "PATH" | "loadDynamicLibrary" | "LDSO"
> & {
  FS: Pick<
    FSType,
    "readdir" | "lookupPath" | "isDir" | "findObject" | "readFile"
  >;
};
