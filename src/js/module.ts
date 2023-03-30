/** @private */

import { ConfigType } from "./pyodide";
import { initializeNativeFS } from "./nativefs";
import { loadBinaryFile } from "./compat";

type FSNode = any;
type FSStream = any;

export interface FS {
  unlink: (path: string) => void;
  mkdirTree: (path: string, mode?: number) => void;
  chdir: (path: string) => void;
  symlink: (target: string, src: string) => FSNode;
  createDevice: (
    parent: string,
    name: string,
    input?: (() => number | null) | null,
    output?: ((code: number) => void) | null,
  ) => FSNode;
  closeStream: (fd: number) => void;
  open: (path: string, flags: string | number, mode?: number) => FSStream;
  makedev: (major: number, minor: number) => number;
  mkdev: (path: string, dev: number) => FSNode;
  filesystems: any;
  stat: (path: string, dontFollow?: boolean) => any;
  readdir: (node: FSNode) => string[];
  isDir: (mode: number) => boolean;
  lookupPath: (path: string) => FSNode;
  isFile: (mode: number) => boolean;
  writeFile: (path: string, contents: any, o?: { canOwn?: boolean }) => void;
  chmod: (path: string, mode: number) => void;
  utime: (path: string, atime: number, mtime: number) => void;
  rmdir: (path: string) => void;
  mount: (type: any, opts: any, mountpoint: string) => any;
  write: (
    stream: FSStream,
    buffer: any,
    offset: number,
    length: number,
    position?: number,
  ) => number;
  close: (stream: FSStream) => void;
}

export interface Module {
  noImageDecoding: boolean;
  noAudioDecoding: boolean;
  noWasmDecoding: boolean;
  quit: (status: number, toThrow: Error) => void;
  preRun: { (): void }[];
  print: (a: string) => void;
  printErr: (a: string) => void;
  ENV: { [key: string]: string };
  PATH: any;
  TTY: any;
  FS: FS;
  canvas?: HTMLCanvasElement;
  addRunDependency: (id: string) => void;
  removeRunDependency: (id: string) => void;
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
  Module.preRun = [];
  Module.quit = (status: number, toThrow: Error) => {
    Module.exited = { status, toThrow };
    throw toThrow;
  };
  return Module;
}

/**
 * Make the home directory inside the virtual file system,
 * then change the working directory to it.
 *
 * @param Module The Emscripten Module.
 * @param path The path to the home directory.
 * @private
 */
function setHomeDirectory(Module: Module, path: string) {
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

/**
 * Mount local directories to the virtual file system. Only for Node.js.
 * @param module The Emscripten Module.
 * @param mounts The list of paths to mount.
 */
function mountLocalDirectories(Module: Module, mounts: string[]) {
  Module.preRun.push(() => {
    for (const mount of mounts) {
      Module.FS.mkdirTree(mount);
      Module.FS.mount(Module.FS.filesystems.NODEFS, { root: mount }, mount);
    }
  });
}

/**
 * Install the Python standard library to the virtual file system.
 *
 * Previously, this was handled by Emscripten's file packager (pyodide.asm.data).
 * However, using the file packager means that we have only one version
 * of the standard library available. We want to be able to use different
 * versions of the standard library, for example:
 *
 * - Use compiled(.pyc) or uncompiled(.py) standard library.
 * - Remove unused modules or add additional modules using bundlers like pyodide-pack.
 *
 * @param Module The Emscripten Module.
 * @param stdlibPromise A promise that resolves to the standard library.
 */
function installStdlib(Module: Module, stdlibURL: string) {
  const stdlibPromise: Promise<Uint8Array> = loadBinaryFile(stdlibURL);

  Module.preRun.push(() => {
    /* @ts-ignore */
    const pymajor = Module._py_version_major();
    /* @ts-ignore */
    const pyminor = Module._py_version_minor();

    Module.FS.mkdirTree("/lib");
    Module.FS.mkdirTree(`/lib/python${pymajor}.${pyminor}/site-packages`);

    Module.addRunDependency("install-stdlib");

    stdlibPromise
      .then((stdlib: Uint8Array) => {
        Module.FS.writeFile(`/lib/python${pymajor}${pyminor}.zip`, stdlib);
      })
      .catch((e) => {
        console.error("Error occurred while installing the standard library:");
        console.error(e);
      })
      .finally(() => {
        Module.removeRunDependency("install-stdlib");
      });
  });
}

/**
 * Initialize the virtual file system, before loading Python interpreter.
 * @private
 */
export function initializeFileSystem(Module: Module, config: ConfigType) {
  let stdLibURL;
  if (config.stdLibURL != undefined) {
    stdLibURL = config.stdLibURL;
  } else {
    stdLibURL = config.indexURL + "python_stdlib.zip";
  }

  installStdlib(Module, stdLibURL);
  setHomeDirectory(Module, config.homedir);
  mountLocalDirectories(Module, config._node_mounts);
  Module.preRun.push(() => initializeNativeFS(Module));
}
