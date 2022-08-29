/** @private */
export interface Module {
  noImageDecoding: boolean;
  noAudioDecoding: boolean;
  noWasmDecoding: boolean;
  quit: (status: number, toThrow: Error) => void;
  preRun: { (): void }[];
  print: (a: string) => void;
  printErr: (a: string) => void;
  ENV: { [key: string]: string };
  preloadedWasm: any;
  FS: any;
}

/**
 * The Emscripten Module.
 *
 * @private
 */
export function createModule(): any {
  let Module: any = {};
  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding = false; // we preload wasm using the built in plugin now
  Module.preloadedWasm = {};
  Module.preRun = [];
  Module.quit = (status: number, toThrow: Error) => {
    Module.exited = { status, toThrow };
    throw toThrow;
  };
  return Module;
}

/**
 *
 * @param stdin
 * @param stdout
 * @param stderr
 * @private
 */
export function setStandardStreams(
  Module: Module,
  stdin?: () => string,
  stdout?: (a: string) => void,
  stderr?: (a: string) => void
) {
  // For stdout and stderr, emscripten provides convenient wrappers that save us the trouble of converting the bytes into a string
  if (stdout) {
    Module.print = stdout;
  }

  if (stderr) {
    Module.printErr = stderr;
  }

  // For stdin, we have to deal with the low level API ourselves
  if (stdin) {
    Module.preRun.push(function () {
      Module.FS.init(createStdinWrapper(stdin), null, null);
    });
  }
}

function createStdinWrapper(stdin: () => string) {
  // When called, it asks the user for one whole line of input (stdin)
  // Then, it passes the individual bytes of the input to emscripten, one after another.
  // And finally, it terminates it with null.
  const encoder = new TextEncoder();
  let input = new Uint8Array(0);
  let inputIndex = -1; // -1 means that we just returned null
  function stdinWrapper() {
    try {
      if (inputIndex === -1) {
        let text = stdin();
        if (text === undefined || text === null) {
          return null;
        }
        if (typeof text !== "string") {
          throw new TypeError(
            `Expected stdin to return string, null, or undefined, got type ${typeof text}.`
          );
        }
        if (!text.endsWith("\n")) {
          text += "\n";
        }
        input = encoder.encode(text);
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
    } catch (e) {
      // emscripten will catch this and set an IOError which is unhelpful for
      // debugging.
      console.error("Error thrown in stdin:");
      console.error(e);
      throw e;
    }
  }
  return stdinWrapper;
}

/**
 * Make the home directory inside the virtual file system,
 * then change the working directory to it.
 *
 * @param path
 * @private
 */
export function setHomeDirectory(Module: Module, path: string) {
  Module.preRun.push(function () {
    const fallbackPath = "/";
    try {
      Module.FS.mkdirTree(path);
    } catch (e) {
      console.error(`Error occurred while making a home directory '${path}':`);
      console.error(e);
      console.error(`Using '${fallbackPath}' for a home directory instead`);
      path = fallbackPath;
    }
    Module.ENV.HOME = path;
    Module.FS.chdir(path);
  });
}
