
{
    let baseURL = "{{DEPLOY}}";
    let wasmURL = baseURL + 'pyodide.asm.wasm?x=' + Date.now();
    let wasmXHR = new XMLHttpRequest();
    wasmXHR.open('GET', wasmURL, true);
    wasmXHR.responseType = 'arraybuffer';
    wasmXHR.onload = function() {
        let Module = {};

        if (wasmXHR.status === 200 || wasmXHR.status === 0) {
            Module.wasmBinary = wasmXHR.response;
        } else {
            alert("Couldn't download the pyodide.asm.wasm binary.  Response was " + wasmXHR.status);
        }

        Module.baseURL = baseURL;
        var script = document.createElement('script');
        script.onload = function() { window.pyodide = pyodide(Module); };
        script.src = baseURL + "pyodide.asm.js";
        document.body.appendChild(script);
    };
    wasmXHR.send(null);
}
