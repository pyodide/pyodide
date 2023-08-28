/** @private */

import { ConfigType } from "./pyodide";
import { initializeNativeFS } from "./nativefs";
import { loadBinaryFile, getBinaryResponse } from "./compat";

export type FSNode = {
  timestamp: number;
  rdev: number;
  contents: Uint8Array;
};

export type FSStream = {
  tty?: boolean;
  seekable?: boolean;
  stream_ops: FSStreamOps;
  node: FSNode;
};

export type FSStreamOps = FSStreamOpsGen<FSStream>;

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

export interface FS {
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
  readdir: (node: FSNode) => string[];
  isDir: (mode: number) => boolean;
  lookupPath: (path: string) => { node: FSNode };
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
}

export interface Module {
  noImageDecoding: boolean;
  noAudioDecoding: boolean;
  noWasmDecoding: boolean;
  quit: (status: number, toThrow: Error) => void;
  preRun: { (): void }[];
  print: (a: string) => void;
  printErr: (a: string) => void;
  ENV: { [key: string]: string };
  PATH: any;
  TTY: any;
  FS: FS;
  canvas?: HTMLCanvasElement;
  addRunDependency: (id: string) => void;
  removeRunDependency: (id: string) => void;
  reportUndefinedSymbols: () => void;
  ERRNO_CODES: { [k: string]: number };
  instantiateWasm?: (
    imports: { [key: string]: any },
    successCallback: (
      instance: WebAssembly.Instance,
      module: WebAssembly.Module,
    ) => void,
  ) => void;
}

/**
 * The Emscripten Module.
 *
 * @private
 */
export function createModule(): any {
  let Module: any = {};
  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding = false; // we preload wasm using the built in plugin now
  Module.preRun = [];
  Module.quit = (status: number, toThrow: Error) => {
    Module.exited = { status, toThrow };
    throw toThrow;
  };
  return Module;
}

/**
 * Make the home directory inside the virtual file system,
 * then change the working directory to it.
 *
 * @param Module The Emscripten Module.
 * @param path The path to the home directory.
 * @private
 */
function createHomeDirectory(Module: Module, path: string) {
  Module.preRun.push(function () {
    const fallbackPath = "/";
    try {
      Module.FS.mkdirTree(path);
    } catch (e) {
      console.error(`Error occurred while making a home directory '${path}':`);
      console.error(e);
      console.error(`Using '${fallbackPath}' for a home directory instead`);
      path = fallbackPath;
    }
    Module.FS.chdir(path);
  });
}

function setEnvironment(Module: Module, env: { [key: string]: string }) {
  Module.preRun.push(function () {
    Object.assign(Module.ENV, env);
  });
}

/**
 * Mount local directories to the virtual file system. Only for Node.js.
 * @param module The Emscripten Module.
 * @param mounts The list of paths to mount.
 */
function mountLocalDirectories(Module: Module, mounts: string[]) {
  Module.preRun.push(() => {
    for (const mount of mounts) {
      Module.FS.mkdirTree(mount);
      Module.FS.mount(Module.FS.filesystems.NODEFS, { root: mount }, mount);
    }
  });
}

/**
 * Install the Python standard library to the virtual file system.
 *
 * Previously, this was handled by Emscripten's file packager (pyodide.asm.data).
 * However, using the file packager means that we have only one version
 * of the standard library available. We want to be able to use different
 * versions of the standard library, for example:
 *
 * - Use compiled(.pyc) or uncompiled(.py) standard library.
 * - Remove unused modules or add additional modules using bundlers like pyodide-pack.
 *
 * @param Module The Emscripten Module.
 * @param stdlibPromise A promise that resolves to the standard library.
 */
function installStdlib(Module: Module, stdlibURL: string) {
  const stdlibPromise: Promise<Uint8Array> = loadBinaryFile(stdlibURL);

  Module.preRun.push(() => {
    /* @ts-ignore */
    const pymajor = Module._py_version_major();
    /* @ts-ignore */
    const pyminor = Module._py_version_minor();

    Module.FS.mkdirTree("/lib");
    Module.FS.mkdirTree(`/lib/python${pymajor}.${pyminor}/site-packages`);

    Module.addRunDependency("install-stdlib");

    stdlibPromise
      .then((stdlib: Uint8Array) => {
        Module.FS.writeFile(`/lib/python${pymajor}${pyminor}.zip`, stdlib);
      })
      .catch((e) => {
        console.error("Error occurred while installing the standard library:");
        console.error(e);
      })
      .finally(() => {
        Module.removeRunDependency("install-stdlib");
      });
  });
}

/**
 * Initialize the virtual file system, before loading Python interpreter.
 * @private
 */
export function initializeFileSystem(Module: Module, config: ConfigType) {
  let stdLibURL;
  if (config.stdLibURL != undefined) {
    stdLibURL = config.stdLibURL;
  } else {
    stdLibURL = config.indexURL + "python_stdlib.zip";
  }

  installStdlib(Module, stdLibURL);
  createHomeDirectory(Module, config.env.HOME);
  setEnvironment(Module, config.env);
  mountLocalDirectories(Module, config._node_mounts);
  Module.preRun.push(() => initializeNativeFS(Module));
}

export function preloadWasm(Module: Module, indexURL: string) {
  if (SOURCEMAP) {
    // According to the docs:
    //
    // "Sanitizers or source map is currently not supported if overriding
    // WebAssembly instantiation with Module.instantiateWasm."
    // https://emscripten.org/docs/api_reference/module.html?highlight=instantiatewasm#Module.instantiateWasm
    return;
  }
  const { binary, response } = getBinaryResponse(indexURL + "pyodide.asm.wasm");
  Module.instantiateWasm = function (
    imports: { [key: string]: any },
    successCallback: (
      instance: WebAssembly.Instance,
      module: WebAssembly.Module,
    ) => void,
  ) {
    (async function () {
      try {
        let res: WebAssembly.WebAssemblyInstantiatedSource;
        if (response) {
          res = await WebAssembly.instantiateStreaming(response, imports);
        } else {
          res = await WebAssembly.instantiate(await binary, imports);
        }
        const { instance, module } = res;
        // When overriding instantiateWasm, in asan builds, we also need
        // to take care of creating the WasmOffsetConverter
        // @ts-ignore
        if (typeof WasmOffsetConverter != "undefined") {
          // @ts-ignore
          wasmOffsetConverter = new WasmOffsetConverter(wasmBinary, module);
        }
        successCallback(instance, module);
      } catch (e) {
        console.warn("wasm instantiation failed!");
        console.warn(e);
      }
    })();

    return {}; // Compiling asynchronously, no exports.
  };
}
