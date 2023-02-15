/** @private */

import { ConfigType } from "./pyodide";

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
 * Create default directories inside the virtual file system.
 * This function is intended to be called before the Pyodide is loaded.
 * @private
 */
export function createDefaultDirectories(Module: Module, config: ConfigType) {
  Module.preRun.push(function () {
    // System directories. Since Python tries to initialize module search paths
    // by checking the existence of these directories, we need to create them
    // before bootstrapping Python.
    Module.FS.mkdirTree("/lib");
    Module.FS.mkdirTree("/usr/lib");

    // Set up the home directory,
    // also change the working directory to it.
    const fallbackPath = "/";
    try {
      Module.FS.mkdirTree(config.homedir);
    } catch (e) {
      console.error(
        `Error occurred while making a home directory '${config.homedir}':`,
      );
      console.error(e);
      console.error(`Using '${fallbackPath}' for a home directory instead`);
      config.homedir = fallbackPath;
    }
    Module.ENV.HOME = config.homedir;
    Module.FS.chdir(config.homedir);

    Module.preRun.push(() => {
      for (const mount of config._node_mounts) {
        Module.FS.mkdirTree(mount);
        Module.FS.mount(Module.FS.filesystems.NODEFS, { root: mount }, mount);
      }
    });
  });
}
