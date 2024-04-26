/** @private */

import { ConfigType } from "./pyodide";
import { initializeNativeFS } from "./nativefs";
import { loadBinaryFile, getBinaryResponse } from "./compat";
import { EmscriptenSettings } from "./types";

/**
 * The Emscripten Module.
 *
 * @private
 */
export function createSettings(): EmscriptenSettings {
  const settings: EmscriptenSettings = {
    noImageDecoding: true,
    noAudioDecoding: true,
    noWasmDecoding: false,
    preRun: [],
    quit(status: number, toThrow: Error) {
      settings.exited = { status, toThrow };
      throw toThrow;
    },
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
function createHomeDirectory(settings: EmscriptenSettings, path: string) {
  settings.preRun.push(function (Module) {
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

function setEnvironment(
  settings: EmscriptenSettings,
  env: { [key: string]: string },
) {
  settings.preRun.push(function (Module) {
    Object.assign(Module.ENV, env);
  });
}

/**
 * Mount local directories to the virtual file system. Only for Node.js.
 * @param module The Emscripten Module.
 * @param mounts The list of paths to mount.
 */
function mountLocalDirectories(settings: EmscriptenSettings, mounts: string[]) {
  settings.preRun.push((Module) => {
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
function installStdlib(settings: EmscriptenSettings, stdlibURL: string) {
  const stdlibPromise: Promise<Uint8Array> = loadBinaryFile(stdlibURL);

  settings.preRun.push((Module) => {
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
export function initializeFileSystem(
  settings: EmscriptenSettings,
  config: ConfigType,
) {
  let stdLibURL;
  if (config.stdLibURL != undefined) {
    stdLibURL = config.stdLibURL;
  } else {
    stdLibURL = config.indexURL + "python_stdlib.zip";
  }

  installStdlib(settings, stdLibURL);
  createHomeDirectory(settings, config.env.HOME);
  setEnvironment(settings, config.env);
  mountLocalDirectories(settings, config._node_mounts);
  settings.preRun.push((Module) => initializeNativeFS(Module));
}

export function preloadWasm(settings: EmscriptenSettings, indexURL: string) {
  if (SOURCEMAP) {
    // According to the docs:
    //
    // "Sanitizers or source map is currently not supported if overriding
    // WebAssembly instantiation with Module.instantiateWasm."
    // https://emscripten.org/docs/api_reference/module.html?highlight=instantiatewasm#Module.instantiateWasm
    return;
  }
  const { binary, response } = getBinaryResponse(indexURL + "pyodide.asm.wasm");
  settings.instantiateWasm = function (
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
