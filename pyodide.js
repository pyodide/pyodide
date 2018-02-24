var Module = {}

{
    let wasmURL = 'pyodide.asm.wasm';
    let wasmXHR = new XMLHttpRequest();
    wasmXHR.open('GET', wasmURL, true);
    wasmXHR.responseType = 'arraybuffer';
    wasmXHR.onload = function() {
        if (wasmXHR.status === 200 || wasmXHR.status === 0) {
            Module.wasmBinary = wasmXHR.response;
        } else {
            var wasmURLBytes = tryParseAsDataURI(wasmURL);
            if (wasmURLBytes) {
                Module.wasmBinary = wasmURLBytes.buffer;
            }
        }

        var memoryInitializer = 'pyodide.asm.html.mem';
        if (typeof Module['locateFile'] === 'function') {
            memoryInitializer = Module['locateFile'](memoryInitializer);
        } else if (Module['memoryInitializerPrefixURL']) {
            memoryInitializer = Module['memoryInitializerPrefixURL'] + memoryInitializer;
        }
        Module['memoryInitializerRequestURL'] = memoryInitializer;
        var meminitXHR = Module['memoryInitializerRequest'] = new XMLHttpRequest();
        meminitXHR.open('GET', memoryInitializer, true);
        meminitXHR.responseType = 'arraybuffer';
        meminitXHR.send(null);

        var script = document.createElement('script');
        script.src = "pyodide.asm.js";
        document.body.appendChild(script);

    };
    wasmXHR.send(null);
}
