/**
 * The Emscripten Module.
 *
 * @private @type {import('emscripten').Module}
 */
export let Module = {};
Module.noImageDecoding = true;
Module.noAudioDecoding = true;
Module.noWasmDecoding = false; // we preload wasm using the built in plugin now
Module.preloadedWasm = {};

/**
 *
 * @param {undefined|(() => string)} stdin
 * @param {undefined|((text: string) => void)} stdout
 * @param {undefined|((text: string) => void)} stderr
 */
export function setStandardStreams(stdin, stdout, stderr) {
  if(stdin) {
    let input = [];
    let inputIndex = -1; // -1 means that we just returned null
    function stdinWrapper() {
      if (inputIndex === -1) {
        input = Module.intArrayFromString((stdin() || "") + "\n", true, 0);
        inputIndex = 0;
      }

      if (inputIndex < input.length) {
        let character = input[inputIndex];
        inputIndex++;
        return character;
      } else {
        inputIndex = -1;
        return null;
      }
    }
    
    Module.preRun = [function() {
      Module.FS.init(stdinWrapper, null, null);
    }];
  }
  
  if(stdout) {
    Module.print = stdout;
  }
  
  if(stderr) {
    Module.printErr = stderr;
  }
}
