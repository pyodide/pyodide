declare global {
  interface Window {
      pyodideArtifactsUrl?: string;
      languagePluginUrl?: string;
      Module?: PyodideModule;
      pyodide: Pyodide,
  }
}

export interface PyodidePackages {
  dependencies: {
    [name: string]: string[]
  },
  import_name_to_package_name: {
    [name: string]: string;
  }
}

export type PyodideModule = {
    // Note: these typings are likely incomplete.

    instantiateWasm(info: any, receiveInstance: (instance: WebAssembly.WebAssemblyInstantiatedSource) => any): Promise<{}>;
    monitorRunDependencies?(n?: number): void;
    loadWebAssemblyModule(path: string, opts: { loadAsync: boolean; }): any;
    locateFile(name: string): string;
    postRun(): Promise<void>;

    preloadedWasm: {
      [path: string]: any;
    }

    FS: any;

    noImageDecoding: boolean,
    noAudioDecoding: boolean,
    noWasmDecoding: boolean,

    packages: PyodidePackages;

    PyProxy: {
      isPyProxy(v: any): boolean
    }

};


export type Pyodide = {
    // Note: these typings are likely incomplete.

    runPython(code: string, messageCallback?: (msg: any) => void, errorCallback?: (err: any) => void): any;
    runPythonAsync(code: string, messageCallback?: (msg: any) => void, errorCallback?: (err: any) => void): Promise<any>;
    loadPackage(names: string[], messageCallback?: (msg: any) => void, errorCallback?: (err: any) => void): Promise<any>;
    loadedPackages: {[name: string]: string};
    globals: any;
    pyimport: (name: string) => any;
    version: () => string;
    autocomplete: any;
    repr?: (v: any) => string;
    _module: PyodideModule;

}
