var pyodide = {}

{
    let wasmURL = 'pyodide.asm.wasm';
    let wasmXHR = new XMLHttpRequest();
    wasmXHR.open('GET', wasmURL, true);
    wasmXHR.responseType = 'arraybuffer';
    wasmXHR.onload = function() {
        if (wasmXHR.status === 200 || wasmXHR.status === 0) {
            pyodide.wasmBinary = wasmXHR.response;
        } else {
            var wasmURLBytes = tryParseAsDataURI(wasmURL);
            if (wasmURLBytes) {
                pyodide.wasmBinary = wasmURLBytes.buffer;
            }
        }

        var memoryInitializer = 'pyodide.asm.html.mem';
        if (typeof pyodide['locateFile'] === 'function') {
            memoryInitializer = pyodide['locateFile'](memoryInitializer);
        } else if (pyodide['memoryInitializerPrefixURL']) {
            memoryInitializer = pyodide['memoryInitializerPrefixURL'] + memoryInitializer;
        }
        pyodide['memoryInitializerRequestURL'] = memoryInitializer;
        var meminitXHR = pyodide['memoryInitializerRequest'] = new XMLHttpRequest();
        meminitXHR.open('GET', memoryInitializer, true);
        meminitXHR.responseType = 'arraybuffer';
        meminitXHR.send(null);

        var script = document.createElement('script');
        script.src = "pyodide.asm.js";
        document.body.appendChild(script);

    };
    wasmXHR.send(null);

    if (window.iodide !== undefined) {
        iodide.addLanguage({
            name: 'py',
            displayName: 'Python',
            keybinding: 'p',
            evaluate: code => pyodide.runPython(code),
        });

        iodide.addOutputHandler({
            shouldHandle: value => (
                value.$$ !== undefined &&
                    value.$$.ptrType.name === 'Py*'
            ),

            render: value => (
                '<span><span role="img" aria-label="py">🐍</span>' +
                    pyodide.repr(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') +
                    '</span>'),
        });
    }
}
