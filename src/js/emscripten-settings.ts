/** @private */

import { PyodideConfigWithDefaults } from "./pyodide";
import { initializeNativeFS } from "./nativefs";
import { initializeNodeSockFS } from "./fs/nodesockfs";
import { loadBinaryFile, getBinaryResponse } from "./compat";
import { API, PreRunFunc, type PyodideModule, type FSType } from "./types";
import { getSentinelImport } from "generated/sentinel";
import { RUNTIME_ENV } from "./environments";
import type { EmscriptenModule } from "./types";

/**
 * @private
 * @hidden
 */
export interface EmscriptenSettings {
  readonly noImageDecoding?: boolean;
  readonly noAudioDecoding?: boolean;
  readonly noWasmDecoding?: boolean;
  readonly preRun: readonly PreRunFunc[];
  readonly print?: (a: string) => void;
  readonly printErr?: (a: string) => void;
  readonly onExit?: (code: number) => void;
  readonly thisProgram?: string;
  readonly arguments: readonly string[];
  readonly instantiateWasm?: (
    imports: { [key: string]: any },
    successCallback: (
      instance: WebAssembly.Instance,
      module: WebAssembly.Module,
    ) => void,
  ) => void;
  readonly API: API;
  readonly locateFile: (file: string) => string;

  noInitialRun?: boolean;
  INITIAL_MEMORY?: number;
  exitCode?: number;
}

/**
 * Get the base settings to use to load Pyodide.
 *
 * @private
 */
export function createSettings(
  config: PyodideConfigWithDefaults,
): EmscriptenSettings {
  const API = { config, runtimeEnv: RUNTIME_ENV } as API;
  const settings: EmscriptenSettings = {
    noImageDecoding: true,
    noAudioDecoding: true,
    noWasmDecoding: false,
    preRun: getFileSystemInitializationFuncs(config),
    print: config.stdout,
    printErr: config.stderr,
    onExit(code) {
      settings.exitCode = code;
    },
    thisProgram: config._sysExecutable,
    arguments: config.args,
    API,
    // Emscripten calls locateFile exactly one time with argument
    // pyodide.asm.wasm to get the URL it should download it from.
    //
    // If we set instantiateWasm the return value of locateFile actually is
    // unused, but Emscripten calls it anyways. We set instantiateWasm except
    // when compiling with source maps, see comment in getInstantiateWasmFunc().
    //
    // It also is called when Emscripten tries to find a dependency of a shared
    // library but it failed to find it in the file system. But for us that
    // means dependency resolution has already failed and we want to throw an
    // error anyways.
    locateFile: (path: string) => config.indexURL + path,
    instantiateWasm: getInstantiateWasmFunc(
      config.indexURL,
      config.withNodeSocket,
    ),
  };
  return settings;
}

/**
 * Make the home directory inside the virtual file system,
 * then change the working directory to it.
 *
 * @param Module The Emscripten Module.
 * @param path The path to the home directory.
 * @private
 */
function createHomeDirectory(path: string): PreRunFunc {
  return function (Module) {
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
  };
}

function setEnvironment(env: { [key: string]: string }): PreRunFunc {
  return function (Module) {
    Object.assign(Module.ENV, env);
  };
}

/**
 * Mount local directories to the virtual file system. Only for Node.js.
 * @param mounts The list of paths to mount.
 */
function callFsInitHook(
  fsInit: undefined | ((fs: FSType, info: { sitePackages: string }) => void),
): PreRunFunc[] {
  if (!fsInit) {
    return [];
  }
  return [
    async (Module) => {
      Module.addRunDependency("fsInitHook");
      try {
        await fsInit(Module.FS, { sitePackages: Module.API.sitePackages });
      } finally {
        Module.removeRunDependency("fsInitHook");
      }
    },
  ];
}

function computeVersionTuple(Module: PyodideModule): [number, number, number] {
  const versionInt = Module.HEAPU32[Module._Py_Version >>> 2];
  const major = (versionInt >>> 24) & 0xff;
  const minor = (versionInt >>> 16) & 0xff;
  const micro = (versionInt >>> 8) & 0xff;
  return [major, minor, micro];
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
 * @param stdlibURL The URL for the Python standard library
 */
function installStdlib(stdlibURL: string): PreRunFunc {
  const stdlibPromise: Promise<Uint8Array> = loadBinaryFile(stdlibURL);
  return async (Module: PyodideModule) => {
    Module.API.pyVersionTuple = computeVersionTuple(Module);
    const [pymajor, pyminor] = Module.API.pyVersionTuple;
    Module.FS.mkdirTree("/lib");
    Module.API.sitePackages = `/lib/python${pymajor}.${pyminor}/site-packages`;
    Module.FS.mkdirTree(Module.API.sitePackages);
    Module.addRunDependency("install-stdlib");

    try {
      const stdlib = await stdlibPromise;
      Module.FS.writeFile(`/lib/python${pymajor}${pyminor}.zip`, stdlib);
    } catch (e) {
      console.error("Error occurred while installing the standard library:");
      console.error(e);
    } finally {
      Module.removeRunDependency("install-stdlib");
    }
  };
}

/**
 * Initialize the virtual file system, before loading Python interpreter.
 * @private
 */
function getFileSystemInitializationFuncs(
  config: PyodideConfigWithDefaults,
): PreRunFunc[] {
  let stdLibURL;
  if (config.stdLibURL != undefined) {
    stdLibURL = config.stdLibURL;
  } else {
    stdLibURL = config.indexURL + "python_stdlib.zip";
  }

  const hooks = [
    installStdlib(stdLibURL),
    createHomeDirectory(config.env.HOME),
    setEnvironment(config.env),
    initializeNativeFS,
    ...callFsInitHook(config.fsInit),
  ];

  if (config.withNodeSocket) {
    hooks.push(...initializeNodeSockFS());
  }

  return hooks;
}

// FIXME:
// Global pyodide module used in wrapSocketSyscallsWithJSPI
// Unlike other functions, functioned wrapped with WebAssembly.suspending in wrapSocketSyscallsWithJSPI
// cannot reference the global `Module` object (don't fully understand why)
// so we need to keep the explicit reference to the module here.
let _pyodideModuleforJSPI: EmscriptenModule | null = null;

/**
 * @private
 */
export function setPyodideModuleforJSPI(module: EmscriptenModule) {
  _pyodideModuleforJSPI = module;
}

/**
 * Wrap socket syscalls with JSPI support.
 * This replaces the syscall imports with versions that can suspend WebAssembly
 * execution while waiting for async socket operations.
 *
 * Note: this function is called before the pyodide WASM module is loaded, so accessing
 *       the global Module object should be done with care.
 */
function wrapSocketSyscallsWithJSPI(imports: {
  [key: string]: { [key: string]: any };
}) {
  if (!RUNTIME_ENV.IN_NODE) {
    DEBUG &&
      console.debug(
        "[wrapSocketSyscallsWithJSPI] Not in Node.js environment, skipping syscall wrapping",
      );
    return;
  }

  const WasmSuspending = (WebAssembly as any).Suspending;
  if (!WasmSuspending) {
    DEBUG &&
      console.debug(
        "WebAssembly.Suspending not available, skipping syscall wrapping",
      );
    return;
  }

  const env = imports.env;
  if (!env) {
    DEBUG && console.debug("No env found, skipping syscall wrapping");
    return;
  }

  const origConnect = env.__syscall_connect;
  const origRecvfrom = env.__syscall_recvfrom;

  if (origConnect) {
    // Create an async version that will be wrapped with WebAssembly.Suspending
    const connectAsync = async (
      fd: number,
      addr: number,
      addrlen: number,
      d1: number,
      d2: number,
      d3: number,
    ): Promise<number> => {
      if (!_pyodideModuleforJSPI) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_connect] Module not found, falling back to original",
          );
        return origConnect(fd, addr, addrlen, d1, d2, d3);
      }

      const SOCKFS = _pyodideModuleforJSPI.SOCKFS;
      const getSocketAddress = _pyodideModuleforJSPI.getSocketAddress;
      if (!SOCKFS || !getSocketAddress) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_connect] SOCKFS or getSocketAddress not found, falling back to original",
          );
        return origConnect(fd, addr, addrlen, d1, d2, d3);
      }

      const sock = SOCKFS.getSocket(fd);
      if (!sock || !sock.sock_ops || !sock.sock_ops.connectAsync) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_connect] Socket not found, falling back to original",
          );
        return origConnect(fd, addr, addrlen, d1, d2, d3);
      }

      try {
        const info = getSocketAddress(addr, addrlen);

        DEBUG &&
          console.debug(
            `[JSPI:__syscall_connect] Using async connect to ${info.addr}:${info.port}`,
          );
        return await sock.sock_ops.connectAsync(sock, info.addr, info.port);
      } catch (e) {
        DEBUG && console.debug("[JSPI:__syscall_connect] Error:", e);
        return origConnect(fd, addr, addrlen, d1, d2, d3);
      }
    };

    // Wrap with WebAssembly.Suspending so it can suspend the WebAssembly stack
    env.__syscall_connect = new WasmSuspending(connectAsync);

    DEBUG &&
      console.debug(
        "[JSPI] Wrapped __syscall_connect with WebAssembly.Suspending",
      );
  }

  if (origRecvfrom) {
    const recvfromAsync = async (
      fd: number,
      buf: number,
      len: number,
      flags: number,
      addr: number,
      addrlen: number,
    ): Promise<number> => {
      if (!_pyodideModuleforJSPI) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_recvfrom] Module not found, falling back to original",
          );
        return origRecvfrom(fd, buf, len, flags, addr, addrlen);
      }

      const SOCKFS = _pyodideModuleforJSPI.SOCKFS;
      const HEAPU8 = _pyodideModuleforJSPI.HEAPU8;

      if (!SOCKFS || !HEAPU8) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_recvfrom] SOCKFS or HEAPU8 not found, falling back to original",
          );
        return origRecvfrom(fd, buf, len, flags, addr, addrlen);
      }

      const sock = SOCKFS.getSocket(fd);
      if (!sock || !sock.sock_ops || !sock.sock_ops.recvmsgAsync) {
        DEBUG &&
          console.debug(
            "[JSPI:__syscall_recvfrom] Socket not found, falling back to original",
          );
        return origRecvfrom(fd, buf, len, flags, addr, addrlen);
      }

      try {
        const result = await sock.sock_ops.recvmsgAsync(sock, len);
        if (result === null) {
          return 0; // EOF
        }
        HEAPU8.set(result.buffer, buf);
        return result.bytesRead;
      } catch (e: any) {
        DEBUG && console.debug("[JSPI:__syscall_recvfrom] Error:", e);
        if (e.name === "ErrnoError") {
          return -e.errno;
        }
        return -5; // EIO
      }
    };

    env.__syscall_recvfrom = new WasmSuspending(recvfromAsync);
    DEBUG &&
      console.debug(
        "[JSPI] Wrapped __syscall_recvfrom with WebAssembly.Suspending",
      );
  }
}

function getInstantiateWasmFunc(
  indexURL: string,
  withNodeSocket: boolean = false,
): EmscriptenSettings["instantiateWasm"] {
  // @ts-ignore
  if (SOURCEMAP || typeof WasmOffsetConverter !== "undefined") {
    // According to the docs:
    //
    // "Sanitizers or source map is currently not supported if overriding
    // WebAssembly instantiation with Module.instantiateWasm."
    // https://emscripten.org/docs/api_reference/module.html?highlight=instantiatewasm#Module.instantiateWasm
    //
    // typeof WasmOffsetConverter !== "undefined" checks for asan.
    return;
  }
  const { binary, response } = getBinaryResponse(indexURL + "pyodide.asm.wasm");
  const sentinelImportPromise = getSentinelImport();
  return function (
    imports: { [key: string]: { [key: string]: any } },
    successCallback: (
      instance: WebAssembly.Instance,
      module: WebAssembly.Module,
    ) => void,
  ) {
    (async function () {
      imports.sentinel = await sentinelImportPromise;

      // Wrap socket syscalls with JSPI support before instantiation
      if (withNodeSocket) {
        wrapSocketSyscallsWithJSPI(imports);
      }

      try {
        let res: WebAssembly.WebAssemblyInstantiatedSource;
        if (response) {
          res = await WebAssembly.instantiateStreaming(response, imports);
        } else {
          res = await WebAssembly.instantiate(await binary, imports);
        }
        const { instance, module } = res;
        successCallback(instance, module);
      } catch (e) {
        console.warn("wasm instantiation failed!");
        console.warn(e);
      }
    })();

    return {}; // Compiling asynchronously, no exports.
  };
}
