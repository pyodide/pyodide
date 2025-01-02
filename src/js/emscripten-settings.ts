/** @private */

import { ConfigType } from "./pyodide";
import { initializeNativeFS } from "./nativefs";
import { loadBinaryFile, getBinaryResponse } from "./compat";
import { API, PreRunFunc } from "./types";

/**
 * @private
 * @hidden
 */
export interface EmscriptenSettings {
  readonly noImageDecoding?: boolean;
  readonly noAudioDecoding?: boolean;
  readonly noWasmDecoding?: boolean;
  readonly preRun: readonly PreRunFunc[];
  readonly quit: (status: number, toThrow: Error) => void;
  readonly print?: (a: string) => void;
  readonly printErr?: (a: string) => void;
  readonly arguments: readonly string[];
  readonly wasmBinary?: ArrayBuffer | Uint8Array;
  readonly instantiateWasm?:
    | false
    | ((
        imports: { [key: string]: any },
        successCallback: (
          instance: WebAssembly.Instance,
          module: WebAssembly.Module,
        ) => void,
      ) => void);
  readonly API: API;
  readonly locateFile: (file: string) => string;

  exited?: { readonly status: number; readonly toThrow: Error };
  noInitialRun?: boolean;
  INITIAL_MEMORY?: number;
}

/**
 * Get the base settings to use to load Pyodide.
 *
 * @private
 */
export function createSettings(config: ConfigType): EmscriptenSettings {
  const settings: EmscriptenSettings = {
    noImageDecoding: true,
    noAudioDecoding: true,
    noWasmDecoding: false,
    preRun: getFileSystemInitializationFuncs(config),
    quit(status: number, toThrow: Error) {
      // It's a little bit hacky that we set this on the settings object but
      // it's not that easy to get access to the Module object from here.
      settings.exited = { status, toThrow };
      throw toThrow;
    },
    print: config.stdout,
    printErr: config.stderr,
    arguments: config.args,
    API: { config } as API,
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
    instantiateWasm: config.emscriptenSettings?.wasmBinary
      ? false
      : getInstantiateWasmFunc(config.indexURL),
  };
  return {
    ...settings,
    ...(config.emscriptenSettings ?? {}),
    preRun: [...settings.preRun, ...(config.emscriptenSettings?.preRun ?? [])],
  };
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
function mountLocalDirectories(mounts: string[]): PreRunFunc {
  return (Module) => {
    for (const mount of mounts) {
      Module.FS.mkdirTree(mount);
      Module.FS.mount(Module.FS.filesystems.NODEFS, { root: mount }, mount);
    }
  };
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
  return (Module) => {
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
  };
}

/**
 * Initialize the virtual file system, before loading Python interpreter.
 * @private
 */
function getFileSystemInitializationFuncs(config: ConfigType): PreRunFunc[] {
  let stdLibURL;
  if (config.stdLibURL != undefined) {
    stdLibURL = config.stdLibURL;
  } else {
    stdLibURL = config.indexURL + "python_stdlib.zip";
  }

  return [
    installStdlib(stdLibURL),
    createHomeDirectory(config.env.HOME),
    setEnvironment(config.env),
    mountLocalDirectories(config._node_mounts),
    initializeNativeFS,
  ];
}

function getInstantiateWasmFunc(
  indexURL: string,
): EmscriptenSettings["instantiateWasm"] {
  if (SOURCEMAP) {
    // According to the docs:
    //
    // "Sanitizers or source map is currently not supported if overriding
    // WebAssembly instantiation with Module.instantiateWasm."
    // https://emscripten.org/docs/api_reference/module.html?highlight=instantiatewasm#Module.instantiateWasm
    //
    // I haven't checked if this is actually a problem in practice.
    return;
  }
  const { binary, response } = getBinaryResponse(indexURL + "pyodide.asm.wasm");
  return function (
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
        if (typeof WasmOffsetConverter !== "undefined") {
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
