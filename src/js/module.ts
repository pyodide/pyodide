/** @private */

import { ConfigType } from "./pyodide";
import { initializeNativeFS } from "./nativefs";

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
 * Initialize the virtual file system, before loading Python interpreter.
 * @private
 */
export function initializeFileSystem(Module: Module, config: ConfigType) {
  setHomeDirectory(Module, config.homedir);
  mountLocalDirectories(Module, config._node_mounts);
  Module.preRun.push(() => initializeNativeFS(Module));
}
