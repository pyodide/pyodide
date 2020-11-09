/**
 * The main bootstrap script for loading pyodide.
 */

import { PyodideModule } from "./types";
import {loadScript, uriToPackageName, fixRecursionLimit, makePublicAPI, preloadWasm, getBaseUrl} from "./util";

const IS_FIREFOX = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

export class PyodideLoader {
    public ready: Promise<this>;
    public baseUrl: string;
  
    private readyPromiseResolve!: () => void;
    private pyodideModule!: PyodideModule;

    /**
     * This promise is used to prevent two packages being loaded asynchronously at the same time.
     */
    private loadPackagePromise: Promise<string | undefined | void> = Promise.resolve();

    constructor() {
        this.ready = new Promise((resolve) => this.readyPromiseResolve = () => resolve(this));
        this.baseUrl = getBaseUrl();
    }

    private async _loadPackage(
        names: string[] = [],
        messageCallback: (message: string) => void = (msg: string) => {console.log(msg)},
        errorCallback: (message: string) => void = (errMsg: string) => {console.error(errMsg)},
    ): Promise<string | undefined> {
        const _messageCallback = (msg: string) => {
          messageCallback(msg);
        };
        const _errorCallback = (errMsg: string) => {
          errorCallback(errMsg);
        };
    
        // DFS to find all dependencies of the requested packages
        const packages = self.pyodide._module.packages.dependencies;
        const loadedPackages = self.pyodide.loadedPackages;
        const queue: string[] = names.slice();
        const toLoad: {[name: string]: string} = {};
        while (queue.length) {
          let packageUri: string = queue.pop()!;
          const pkg = uriToPackageName(packageUri);
    
          if (pkg == null) {
            _errorCallback(`Invalid package name or URI '${packageUri}'`);
            return;
          } else if (pkg == packageUri) {
            packageUri = 'default channel';
          }
    
          if (pkg in loadedPackages) {
            if (packageUri != loadedPackages[pkg]) {
              _errorCallback(`URI mismatch, attempting to load package ` +
                            `${pkg} from ${packageUri} while it is already ` +
                            `loaded from ${loadedPackages[pkg]}!`);
              return;
            } else {
              // _messageCallback(`${pkg} already loaded from ${loadedPackages[pkg]}`)
            }
          } else if (pkg in toLoad) {
            if (packageUri != toLoad[pkg]) {
              _errorCallback(`URI mismatch, attempting to load package ` +
                            `${pkg} from ${packageUri} while it is already ` +
                            `being loaded from ${toLoad[pkg]}!`);
              return;
            }
          } else {
            // console.log(`${pkg} to be loaded from ${package_uri}`); // debug level info.
    
            toLoad[pkg] = packageUri;
            if (packages.hasOwnProperty(pkg)) {
              packages[pkg].forEach((subPackage: string) => {
                if (!(subPackage in loadedPackages) && !(subPackage in toLoad)) {
                  queue.push(subPackage);
                }
              });
            } else {
              _errorCallback(`Unknown package '${pkg}'`);
            }
          }
        }

        self.pyodide._module.locateFile = (path: string) => {
            // handle packages loaded from custom URLs
            const pkg = path.replace(/\.data$/, "");
            if (pkg in toLoad) {
              const packageUri = toLoad[pkg];
              if (packageUri != 'default channel') {
                return packageUri.replace(/\.js$/, ".data");
              };
            };
            return this.baseUrl + path;
        };


        const promise: Promise<string> = new Promise((resolve, reject) => {
            if (Object.keys(toLoad).length === 0) {
              resolve('No new packages to load');
              return 'No new packages to load';
            }
      
            const packageList = Array.from(Object.keys(toLoad));
            _messageCallback(`Loading ${packageList.join(', ')}`)
      
            // monitorRunDependencies is called at the beginning and the end of each
            // package being loaded. We know we are done when it has been called
            // exactly "toLoad * 2" times.
            var packageCounter = Object.keys(toLoad).length * 2;

            // Add a handler for any exceptions that are thrown in the process of
            // loading a package
            const windowErrorHandler = (err: any) => {
                delete self.pyodide._module.monitorRunDependencies;
                self.removeEventListener('error', windowErrorHandler);
                // Set up a new Promise chain, since this one failed
                this.loadPackagePromise = new Promise((resolve) => resolve());
                reject(err.message);
            };
      
            self.pyodide._module.monitorRunDependencies = () => {
              packageCounter--;
              if (packageCounter === 0) {
                for (const pkg in toLoad) {
                  self.pyodide.loadedPackages[pkg] = toLoad[pkg];
                }
                delete self.pyodide._module.monitorRunDependencies;
                self.removeEventListener('error', windowErrorHandler);
      
                let resolveMsg = `Loaded `;
                if (packageList.length > 0) {
                  resolveMsg += packageList.join(', ');
                } else {
                  resolveMsg += 'no packages'
                }
      
                if (!IS_FIREFOX) {
                  preloadWasm(this.pyodideModule).then(() => {
                    console.log(resolveMsg);
                    resolve(resolveMsg);
                  });
                } else {
                  console.log(resolveMsg);
                  resolve(resolveMsg);
                }
              }
            };
      
            self.addEventListener('error', windowErrorHandler);
      
            for (const pkg in toLoad) {
              let scriptSrc: string;
              const packageUri = toLoad[pkg];
              if (packageUri == 'default channel') {
                scriptSrc = `${this.baseUrl}${pkg}.js`;
              } else {
                scriptSrc = `${packageUri}`;
              }
              // _messageCallback(`Loading ${pkg} from ${scriptSrc}`)
              loadScript(scriptSrc, () => {}, () => {
                // If the packageUri fails to load, call monitorRunDependencies twice
                // (so packageCounter will still hit 0 and finish loading), and remove
                // the package from toLoad so we don't mark it as loaded, and remove
                // the package from packageList so we don't say that it was loaded.
                _errorCallback(`Couldn't load package from URL ${scriptSrc}`);
                delete toLoad[pkg];
                const packageListIndex = packageList.indexOf(pkg);
                if (packageListIndex !== -1) {
                  packageList.splice(packageListIndex, 1);
                }
                for (let i = 0; i < 2; i++) {
                  self.pyodide._module.monitorRunDependencies!();
                }
              });
            }
      
            // We have to invalidate Python's import caches, or it won't
            // see the new files. This is done here so it happens in parallel
            // with the fetching over the network.
            self.pyodide.runPython('import importlib as _importlib\n' +
                                  '_importlib.invalidate_caches()\n');
        });
      
        return promise;
    }

    public loadPackage(names: string[], messageCallback?: (message: string) => void, errorCallback?: (message: string) => void) {
        /* We want to make sure that only one loadPackage invocation runs at any
        * given time, so this creates a "chain" of promises. */
        this.loadPackagePromise = this.loadPackagePromise.then(
            () => this._loadPackage(names, messageCallback, errorCallback));
        return this.loadPackagePromise;
    }

    private createModule() {
      const module: any = {
        noImageDecoding: true,
        noAudioDecoding: true,
        noWasmDecoding: true,
        preloadedWasm: {},
      }

      module.checkABI = (AbiNumber: number) => {
        if (AbiNumber !== parseInt('1')) {
        const AbiMismatchException =
            `ABI numbers differ. Expected 1, got ${AbiNumber}`;
        console.error(AbiMismatchException);
        throw AbiMismatchException;
        }
        return true;
      }

      module.autocomplete = (path: string) => {
        const pyodideModule = module.pyimport("pyodide");
        return pyodideModule.get_completions(path);
      }

      module.locateFile = (path: string) => this.baseUrl + path;
      return module;
    }


    public async setup() {
        const wasmUrl = `${this.baseUrl}pyodide.asm.wasm`;
        this.pyodideModule = this.createModule();

        // This global is used in one of the imported scripts.
        // it gets deleted in Module.postRun()
        self.Module = this.pyodideModule;

        let wasmPromise: any;
        const wasmFetch = fetch(wasmUrl);

        if (WebAssembly.compileStreaming === undefined) {
            wasmPromise = new Promise(async (resolve) => {
              const bytes = await (await wasmFetch).arrayBuffer();
              resolve(WebAssembly.compile(bytes));
            });
        } else {
          wasmPromise = WebAssembly.compileStreaming(wasmFetch);
        }
  
        this.pyodideModule.instantiateWasm = async (info, receiveInstance) => {
            receiveInstance(await WebAssembly.instantiate(await wasmPromise, info));
            return {};
        };
        
        
        const postRunPromise = new Promise((resolve, reject) => {
            this.pyodideModule.postRun = async () => {
                delete self.Module;
                const json = await (await fetch(`${this.baseUrl}packages.json`)).json();
                fixRecursionLimit(self.pyodide);
                self.pyodide.globals = self.pyodide.runPython('import sys\nsys.modules["__main__"]');
                (self.pyodide as any) = makePublicAPI(self.pyodide);
                self.pyodide._module.packages = json;
                resolve();
            };
        });
        
        const dataLoadPromise = new Promise((resolve, reject) => {
            this.pyodideModule.monitorRunDependencies =
                (n: number) => {
                  if (n === 0) {
                      delete this.pyodideModule.monitorRunDependencies;
                      resolve();
                  }
                }
        });

        const promises = Promise.all([ postRunPromise, dataLoadPromise ]);
    
        const dataScriptSrc = `${this.baseUrl}pyodide.asm.data.js`;
        loadScript(dataScriptSrc, () => {
            const scriptSrc = `${this.baseUrl}pyodide.asm.js`;
            loadScript(scriptSrc, () => {
                // The emscripten module needs to be at this location for the core
                // filesystem to install itself. Once that's complete, it will be replaced
                // by the call to `makePublicAPI` with a more limited public API.
                self.pyodide = (self.pyodide as any)(this.pyodideModule); // TODO type this better
                self.pyodide.loadedPackages = {};
                self.pyodide.loadPackage = (...v) => this.loadPackage(...v);
            }, () => {});
        }, () => {});

        await promises;
        this.readyPromiseResolve();
    }
}
