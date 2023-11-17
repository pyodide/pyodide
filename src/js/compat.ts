import ErrorStackParser from "error-stack-parser";
import {
  IN_NODE,
  IN_NODE_ESM,
  IN_BROWSER_MAIN_THREAD,
  IN_BROWSER_WEB_WORKER,
  IN_NODE_COMMONJS,
} from "./environments";

let nodeUrlMod: any;
let nodeFetch: any;
let nodePath: any;
let nodeVmMod: any;
/** @private */
export let nodeFsPromisesMod: any;

declare var globalThis: {
  importScripts: (url: string) => void;
  document?: any;
  fetch?: any;
};

const FETCH_NOT_FOUND_MSG = `\
"fetch" is not defined, maybe you're using node < 18? \
From Pyodide >= 0.25.0, node >= 18 is required. \
Older versions of Node.js may work, but it is not guaranteed or supported. \
Falling back to "node-fetch".\
`;

/**
 * If we're in node, it's most convenient to import various node modules on
 * initialization. Otherwise, this does nothing.
 * @private
 */
export async function initNodeModules() {
  if (!IN_NODE) {
    return;
  }
  // @ts-ignore
  nodeUrlMod = (await import("url")).default;
  nodeFsPromisesMod = await import("fs/promises");
  if (globalThis.fetch) {
    nodeFetch = fetch;
  } else {
    // @ts-ignore
    console.warn(FETCH_NOT_FOUND_MSG);
    // @ts-ignore
    nodeFetch = (await import("node-fetch")).default;
  }
  // @ts-ignore
  nodeVmMod = (await import("vm")).default;
  nodePath = await import("path");
  pathSep = nodePath.sep;

  // Emscripten uses `require`, so if it's missing (because we were imported as
  // an ES6 module) we need to polyfill `require` with `import`. `import` is
  // async and `require` is synchronous, so we import all packages that might be
  // required up front and define require to look them up in this table.

  if (typeof require !== "undefined") {
    return;
  }
  // These are all the packages required in pyodide.asm.js. You can get this
  // list with:
  // $ grep -o 'require("[a-z]*")' pyodide.asm.js  | sort -u
  const fs = await import("fs");
  const crypto = await import("crypto");
  const ws = await import("ws");
  const child_process = await import("child_process");
  const node_modules: { [mode: string]: any } = {
    fs,
    crypto,
    ws,
    child_process,
  };
  // Since we're in an ES6 module, this is only modifying the module namespace,
  // it's still private to Pyodide.
  (globalThis as any).require = function (mod: string): any {
    return node_modules[mod];
  };
}

function node_resolvePath(path: string, base?: string): string {
  return nodePath.resolve(base || ".", path);
}

function browser_resolvePath(path: string, base?: string): string {
  if (base === undefined) {
    // @ts-ignore
    base = location;
  }
  return new URL(path, base).toString();
}

export let resolvePath: (rest: string, base?: string) => string;
if (IN_NODE) {
  resolvePath = node_resolvePath;
} else {
  resolvePath = browser_resolvePath;
}

/**
 * Get the path separator. If we are on Linux or in the browser, it's /.
 * In Windows, it's \.
 * @private
 */
export let pathSep: string;

if (!IN_NODE) {
  pathSep = "/";
}

/**
 * Load a binary file, only for use in Node. If the path explicitly is a URL,
 * then fetch from a URL, else load from the file system.
 * @param indexURL base path to resolve relative paths
 * @param path the path to load
 * @param checksum sha-256 checksum of the package
 * @returns An ArrayBuffer containing the binary data
 * @private
 */
function node_getBinaryResponse(
  path: string,
  _file_sub_resource_hash?: string | undefined, // Ignoring sub resource hash. See issue-2431.
):
  | { response: Promise<Response>; binary?: undefined }
  | { binary: Promise<Uint8Array> } {
  if (path.startsWith("file://")) {
    // handle file:// with filesystem operations rather than with fetch.
    path = path.slice("file://".length);
  }
  if (path.includes("://")) {
    // If it has a protocol, make a fetch request
    return { response: nodeFetch(path) };
  } else {
    // Otherwise get it from the file system
    return {
      binary: nodeFsPromisesMod
        .readFile(path)
        .then(
          (data: Buffer) =>
            new Uint8Array(data.buffer, data.byteOffset, data.byteLength),
        ),
    };
  }
}

/**
 * Load a binary file, only for use in browser. Resolves relative paths against
 * indexURL.
 *
 * @param path the path to load
 * @param subResourceHash the sub resource hash for fetch() integrity check
 * @returns A Uint8Array containing the binary data
 * @private
 */
function browser_getBinaryResponse(
  path: string,
  subResourceHash: string | undefined,
): { response: Promise<Response>; binary?: undefined } {
  const url = new URL(path, location as unknown as URL);
  let options = subResourceHash ? { integrity: subResourceHash } : {};
  return { response: fetch(url, options) };
}

/** @private */
export let getBinaryResponse: (
  path: string,
  file_sub_resource_hash?: string | undefined,
) =>
  | { response: Promise<Response>; binary?: undefined }
  | { response?: undefined; binary: Promise<Uint8Array> };
if (IN_NODE) {
  getBinaryResponse = node_getBinaryResponse;
} else {
  getBinaryResponse = browser_getBinaryResponse;
}

export async function loadBinaryFile(
  path: string,
  file_sub_resource_hash?: string | undefined,
): Promise<Uint8Array> {
  const { response, binary } = getBinaryResponse(path, file_sub_resource_hash);
  if (binary) {
    return binary;
  }
  const r = await response;
  if (!r.ok) {
    throw new Error(`Failed to load '${path}': request failed.`);
  }
  return new Uint8Array(await r.arrayBuffer());
}

/**
 * Currently loadScript is only used once to load `pyodide.asm.js`.
 * @param url
 * @async
 * @private
 */
export let loadScript: (url: string) => Promise<void>;

if (IN_BROWSER_MAIN_THREAD) {
  // browser
  loadScript = async (url) => await import(/* webpackIgnore: true */ url);
} else if (IN_BROWSER_WEB_WORKER) {
  // webworker
  loadScript = async (url) => {
    try {
      // use importScripts in classic web worker
      globalThis.importScripts(url);
    } catch (e) {
      // importScripts throws TypeError in a module type web worker, use import instead
      if (e instanceof TypeError) {
        await import(/* webpackIgnore: true */ url);
      } else {
        throw e;
      }
    }
  };
} else if (IN_NODE) {
  loadScript = nodeLoadScript;
} else {
  throw new Error("Cannot determine runtime environment");
}

/**
 * Load a text file and executes it as Javascript
 * @param url The path to load. May be a url or a relative file system path.
 * @private
 */
async function nodeLoadScript(url: string) {
  if (url.startsWith("file://")) {
    // handle file:// with filesystem operations rather than with fetch.
    url = url.slice("file://".length);
  }
  if (url.includes("://")) {
    // If it's a url, load it with fetch then eval it.
    nodeVmMod.runInThisContext(await (await nodeFetch(url)).text());
  } else {
    // Otherwise, hopefully it is a relative path we can load from the file
    // system.
    await import(/* webpackIgnore: true */ nodeUrlMod.pathToFileURL(url).href);
  }
}

// consider dropping this this once we drop support for node 14?
function nodeBase16ToBase64(b16: string): string {
  return Buffer.from(b16, "hex").toString("base64");
}

function browserBase16ToBase64(b16: string): string {
  return btoa(
    b16
      .match(/\w{2}/g)!
      .map(function (a) {
        return String.fromCharCode(parseInt(a, 16));
      })
      .join(""),
  );
}

export const base16ToBase64 = IN_NODE
  ? nodeBase16ToBase64
  : browserBase16ToBase64;

export async function loadLockFile(lockFileURL: string): Promise<any> {
  if (IN_NODE) {
    await initNodeModules();
    const package_string = await nodeFsPromisesMod.readFile(lockFileURL);
    return JSON.parse(package_string);
  } else {
    let response = await fetch(lockFileURL);
    return await response.json();
  }
}

/**
 * Calculate the directory name of the current module.
 * This is used to guess the indexURL when it is not provided.
 */
export async function calculateDirname(): Promise<string> {
  if (IN_NODE_COMMONJS) {
    return __dirname;
  }

  let err: Error;
  try {
    throw new Error();
  } catch (e) {
    err = e as Error;
  }
  let fileName = ErrorStackParser.parse(err)[0].fileName!;

  if (IN_NODE_ESM) {
    const nodePath = await import("path");
    const nodeUrl = await import("url");

    // FIXME: We would like to use import.meta.url here,
    // but mocha seems to mess with compiling typescript files to ES6.
    return nodeUrl.fileURLToPath(nodePath.dirname(fileName));
  }

  const indexOfLastSlash = fileName.lastIndexOf(pathSep);
  if (indexOfLastSlash === -1) {
    throw new Error(
      "Could not extract indexURL path from pyodide module location",
    );
  }
  return fileName.slice(0, indexOfLastSlash);
}
