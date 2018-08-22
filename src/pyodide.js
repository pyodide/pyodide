/**
 * The main bootstrap script for loading pyodide.
 */

// Regexp for validating package name and URI
var package_name_regexp = '[a-zA-Z0-9_\-]+'
var package_uri_regexp = new RegExp(
     '^(?:https?|file)://.*?(' + package_name_regexp + ').js$');
var package_name_regexp = new RegExp('^' + package_name_regexp + '$');


var languagePluginLoader = new Promise((resolve, reject) => {
  // This is filled in by the Makefile to be either a local file or the
  // deployed location. TODO: This should be done in a less hacky
  // way.
  const baseURL = '{{DEPLOY}}';

  ////////////////////////////////////////////////////////////
  // Package loading
  var packages = undefined;
  let loadedPackages = new Array();

  let _uri_to_package_name = (package_uri) => {
    // Generate a unique package name from URI

    if (package_name_regexp.test(package_uri)) {
      return package_uri;
    } else if (package_uri_regexp.test(package_uri)) {
      var match = package_uri_regexp.exec(package_uri);
      // Get the regexp group corresponding to the package name
      return match[1];
    } else {
      return null;
    }
  };


  let loadPackage = (names) => {
    // DFS to find all dependencies of the requested packages
    let packages = window.pyodide.packages.dependencies;
    let queue = new Array(names);
    let toLoad = new Set();
    while (queue.length) {
      var package_uri = queue.pop();

      const package = _uri_to_package_name(package_uri);

      if (package == null) {
          console.log(`Invalid package name or URI '${package_uri}'`);
          break;
      }  else if (package == package_uri) {
          package_uri = 'packages.json';
      }

      console.log(`Loading ${package} from ${package_uri}`);

      if (package in loadedPackages) {
        if (package_uri != loadedPackages[package]) {
          console.log(`Error: URI mismatch, attempting to load package ` +
                      `${package} from ${package_uri} while is already ` +
                      `loaded from ${loadedPackages[package]}!`);
        }
      } else {
        toLoad.add(package);
        if (packages.hasOwnProperty(package)) {
          packages[package].forEach((subpackage) => {
            if (!(subpackage in loadedPackages) && !toLoad.has(subpackage)) {
              queue.push(subpackage);
            }
          });
        } else {
          console.log(`Unknown package '${package}'`);
        }
      }
    }

    let promise = new Promise((resolve, reject) => {
      if (toLoad.size === 0) {
        resolve('No new packages to load');
      }

      pyodide.monitorRunDependencies = (n) => {
        if (n === 0) {
          toLoad.forEach((package) => {
              loadedPackages[package] = package;
          });
          delete pyodide.monitorRunDependencies;
          const packageList = Array.from(toLoad.keys()).join(', ');
          resolve(`Loaded ${packageList}`);
        }
      };

      toLoad.forEach((package) => {
        let script = document.createElement('script');
        script.src = `${baseURL}${package}.js`;
        script.onerror = (e) => { reject(e); };
        document.body.appendChild(script);
      });

      // We have to invalidate Python's import caches, or it won't
      // see the new files. This is done here so it happens in parallel
      // with the fetching over the network.
      window.pyodide.runPython('import importlib as _importlib\n' +
                               '_importlib.invalidate_caches()\n');
    });

    if (window.iodide !== undefined) {
      window.iodide.evalQueue.await([ promise ]);
    }

    return promise;
  };

  function fixRecursionLimit(pyodide) {
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
    pyodide.runPython(
        `import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
  };

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  let wasmURL = `${baseURL}pyodide.asm.wasm`;
  let Module = {};
  window.Module = Module;

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
  if (isFirefox) {
    console.log("Skipping wasm decoding");
    Module.noWasmDecoding = true;
  }

  let wasm_promise = WebAssembly.compileStreaming(fetch(wasmURL));
  Module.instantiateWasm = (info, receiveInstance) => {
    wasm_promise.then(module => WebAssembly.instantiate(module, info))
        .then(instance => receiveInstance(instance));
    return {};
  };

  Module.filePackagePrefixURL = baseURL;
  Module.locateFile = (path) => baseURL + path;
  var postRunPromise = new Promise((resolve, reject) => {
    Module.postRun = () => {
      delete window.Module;
      fetch(`${baseURL}packages.json`)
          .then((response) => response.json())
          .then((json) => {
            window.pyodide.packages = json;
            fixRecursionLimit(pyodide);
            resolve();
          });
    };
  });

  var dataLoadPromise = new Promise((resolve, reject) => {
    Module.monitorRunDependencies =
        (n) => {
          if (n === 0) {
            delete Module.monitorRunDependencies;
            resolve();
          }
        }
  });

  Promise.all([ postRunPromise, dataLoadPromise ]).then(() => resolve());

  let data_script = document.createElement('script');
  data_script.src = `${baseURL}pyodide.asm.data.js`;
  data_script.onload = (event) => {
    let script = document.createElement('script');
    script.src = `${baseURL}pyodide.asm.js`;
    script.onload = () => {
      window.pyodide = pyodide(Module);
      window.pyodide.loadPackage = loadPackage;
    };
    document.head.appendChild(script);
  };

  document.head.appendChild(data_script);

  ////////////////////////////////////////////////////////////
  // Iodide-specific functionality, that doesn't make sense
  // if not using with Iodide.
  if (window.iodide !== undefined) {
    // Load the custom CSS for Pyodide
    let link = document.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = `${baseURL}renderedhtml.css`;
    document.getElementsByTagName('head')[0].appendChild(link);

    // Add a custom output handler for Python objects
    window.iodide.addOutputHandler({
      shouldHandle : (val) => {
        return (typeof val === 'function' && pyodide.PyProxy.isPyProxy(val));
      },

      render : (val) => {
        let div = document.createElement('div');
        div.className = 'rendered_html';
        var element;
        if (val._repr_html_ !== undefined) {
          let result = val._repr_html_();
          if (typeof result === 'string') {
            div.appendChild(new DOMParser()
                                .parseFromString(result, 'text/html')
                                .body.firstChild);
            element = div;
          } else {
            element = result;
          }
        } else {
          let pre = document.createElement('pre');
          pre.textContent = val.toString();
          div.appendChild(pre);
          element = div;
        }
        return element;
      }
    });
  }
});
languagePluginLoader
