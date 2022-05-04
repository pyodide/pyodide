// Detect if we're in node
declare var process: any;

export const IN_NODE =
  typeof process !== "undefined" &&
  process.release &&
  process.release.name === "node" &&
  typeof process.browser ===
    "undefined"; /* This last condition checks if we run the browser shim of process */

let nodePathMod: any;
let nodeFetch: any;
let nodeVmMod: any;
/** @private */
export let nodeFsPromisesMod: any;

declare var globalThis: {
  importScripts: (url: string) => void;
  document?: any;
};

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
  nodePathMod = (await import("path")).default;
  nodeFsPromisesMod = await import("fs/promises");
  // @ts-ignore
  nodeFetch = (await import("node-fetch")).default;
  // @ts-ignore
  nodeVmMod = (await import("vm")).default;
  if (typeof require !== "undefined") {
    return;
  }
  // Emscripten uses `require`, so if it's missing (because we were imported as
  // an ES6 module) we need to polyfill `require` with `import`. `import` is
  // async and `require` is synchronous, so we import all packages that might be
  // required up front and define require to look them up in this table.

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

/**
 * Load a binary file, only for use in Node. If the path explicitly is a URL,
 * then fetch from a URL, else load from the file system.
 * @param indexURL base path to resolve relative paths
 * @param path the path to load
 * @returns An ArrayBuffer containing the binary data
 * @private
 */
async function node_loadBinaryFile(
  indexURL: string,
  path: string
): Promise<Uint8Array> {
  if (!path.startsWith("/") && !path.includes("://")) {
    // If path starts with a "/" or starts with a protocol "blah://", we
    // interpret it as an absolute path, otherwise "resolve" it by
    // joining it with indexURL.
    path = `${indexURL}${path}`;
  }
  if (path.startsWith("file://")) {
    // handle file:// with filesystem operations rather than with fetch.
    path = path.slice("file://".length);
  }
  if (path.includes("://")) {
    // If it has a protocol, make a fetch request
    let response = await nodeFetch(path);
    if (!response.ok) {
      throw new Error(`Failed to load '${path}': request failed.`);
    }
    return new Uint8Array(await response.arrayBuffer());
  } else {
    // Otherwise get it from the file system
    const data = await nodeFsPromisesMod.readFile(path);
    return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  }
}

/**
 * Load a binary file, only for use in browser. Resolves relative paths against
 * indexURL.
 *
 * @param indexURL base path to resolve relative paths
 * @param path the path to load
 * @returns A Uint8Array containing the binary data
 * @private
 */
async function browser_loadBinaryFile(
  indexURL: string,
  path: string
): Promise<Uint8Array> {
  // @ts-ignore
  const base = new URL(indexURL, location);
  const url = new URL(path, base);
  // @ts-ignore
  let response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load '${url}': request failed.`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

/** @private */
export let _loadBinaryFile: (
  indexURL: string,
  path: string
) => Promise<Uint8Array>;
if (IN_NODE) {
  _loadBinaryFile = node_loadBinaryFile;
} else {
  _loadBinaryFile = browser_loadBinaryFile;
}

/**
 * Currently loadScript is only used once to load `pyodide.asm.js`.
 * @param url
 * @async
 * @private
 */
export let loadScript: (url: string) => Promise<void>;

if (globalThis.document) {
  // browser
  loadScript = async (url) => await import(url);
} else if (globalThis.importScripts) {
  // webworker
  loadScript = async (url) => {
    // This is async only for consistency
    try {
      // use importScripts in classic web worker
      globalThis.importScripts(url);
    } catch (e) {
      // importScripts throws TypeError in a module type web worker, use import instead
      if (e instanceof TypeError) {
        await import(url);
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
    await import(nodePathMod.resolve(url));
  }
}
