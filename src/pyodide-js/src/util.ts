import { PyodideModule } from "./types";

// Regexp for validating package name and URI
const PACKAGE_REGEX = '[a-z0-9_][a-z0-9_\-]*';
const PACKAGE_URI_REGEXP = new RegExp('^https?://.*?(' + PACKAGE_REGEX + ').js$', 'i');
const PACKAGE_NAME_REGEXP = new RegExp('^' + PACKAGE_REGEX + '$', 'i');

const PUBLIC_API = [
  'globals',
  'loadPackage',
  'loadedPackages',
  'pyimport',
  'repr',
  'runPython',
  'runPythonAsync',
  'checkABI',
  'version',
  'autocomplete',
];

export function uriToPackageName(packageUri: string) {
    // Generate a unique package name from URI
    if (PACKAGE_NAME_REGEXP.test(packageUri)) {
      return packageUri;
    }
    const matches = PACKAGE_URI_REGEXP.exec(packageUri)
    if (matches !== null) {
      // Get the regexp group corresponding to the package name
      return matches[1];
    } else {
      return null;
    }
}

export function getBaseUrl() {
  var baseUrl = self.pyodideArtifactsUrl || self.languagePluginUrl  || '__PYODIDE_BASE_URL__';
  baseUrl = baseUrl.substr(0, baseUrl.lastIndexOf('/')) + '/';
  return baseUrl;
}

export function loadScript(url: string, onload: () => any, onerror: () => any) {
    if (self.document) { // browser
      const script = self.document.createElement('script');
      script.src = url;
      script.onload = (e) => { onload(); };
      script.onerror = (e: string | Event) => { onerror(); };
      self.document.head.appendChild(script);
    } else if ((self as any).importScripts) { // webworker
      try {
        (self as any).importScripts(url);
        onload();
      } catch {
        onerror();
      }
    }
  }

export function fixRecursionLimit(pyodide: {runPython: (code: string) => any}) {
    // The Javascript/Wasm call stack may be too small to handle the default
    // Python call stack limit of 1000 frames. This is generally the case on
    // Chrom(ium), but not on Firefox. Here, we determine the Javascript call
    // stack depth available, and then divide by 50 (determined heuristically)
    // to set the maximum Python call stack depth.
    let depth = 0;
    function recurse() {
      depth += 1;
      recurse();
    }
    try {
      recurse();
    } catch (err) {
      ;
    }

    let recursionLimit = depth / 50;
    if (recursionLimit > 1000) {
      recursionLimit = 1000;
    }
    pyodide.runPython(`import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
};

export function makePublicAPI(module: any) {
  const namespace: {_module: any, [key: string]: any} = {_module : module};
  for (const name of PUBLIC_API) {
    namespace[name] = module[name];
  }
  return namespace;
}

export async function preloadWasm(pyodideModule: PyodideModule) {
  const FS = self.pyodide._module.FS;
  const recurseDir = async (rootPath: string) => {
    let dirs;
    try {
      dirs = FS.readdir(rootPath);
    } catch {
      return;
    }
    for (let entry of dirs) {
      if (entry.startsWith('.')) {
        continue;
      }
      const path = rootPath + entry;
      if (entry.endsWith('.so')) {
        if (pyodideModule.preloadedWasm[path] === undefined) {
          pyodideModule.preloadedWasm[path] = await pyodideModule.loadWebAssemblyModule(FS.readFile(path), {loadAsync: true});
        }
      } else if (FS.isDir(FS.lookupPath(path).node.mode)) {
        await recurseDir(path + '/');
      }
    }
  }
  await recurseDir('/');
}
