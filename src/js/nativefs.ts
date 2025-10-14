import { PyodideModule } from "./types";

/**
 * @private
 */
async function syncfs(m: PyodideModule, direction: boolean): Promise<void> {
  return new Promise((resolve, reject) => {
    m.FS.syncfs(direction, (err: any) => {
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    });
  });
}

/**
 * @private
 */
export async function syncLocalToRemote(m: PyodideModule): Promise<void> {
  return await syncfs(m, false);
}

/**
 * @private
 */
export async function syncRemoteToLocal(m: PyodideModule): Promise<void> {
  return await syncfs(m, true);
}

/**
 * @private
 */
export function initializeNativeFS(module: PyodideModule) {
  const FS = module.FS;
  const MEMFS = module.FS.filesystems.MEMFS;
  const PATH = module.PATH;

  const nativeFSAsync = {
    // DIR_MODE: {{{ cDefine('S_IFDIR') }}} | 511 /* 0777 */,
    // FILE_MODE: {{{ cDefine('S_IFREG') }}} | 511 /* 0777 */,
    DIR_MODE: 16384 | 511,
    FILE_MODE: 32768 | 511,
    mount: function (mount: any) {
      if (!mount.opts.fileSystemHandle) {
        throw new Error("opts.fileSystemHandle is required");
      }

      // reuse all of the core MEMFS functionality
      return MEMFS.mount.apply(null, arguments);
    },
    syncfs: async (mount: any, populate: Boolean, callback: Function) => {
      try {
        const local = nativeFSAsync.getLocalSet(mount);
        const remote = await nativeFSAsync.getRemoteSet(mount);
        const src = populate ? remote : local;
        const dst = populate ? local : remote;
        await nativeFSAsync.reconcile(mount, src, dst);
        callback(null);
      } catch (e) {
        callback(e);
      }
    },
    // Returns file set of emscripten's filesystem at the mountpoint.
    getLocalSet: (mount: any) => {
      let entries = Object.create(null);

      function isRealDir(p: string) {
        return p !== "." && p !== "..";
      }

      function toAbsolute(root: string) {
        return (p: string) => {
          return PATH.join2(root, p);
        };
      }

      let check = FS.readdir(mount.mountpoint)
        .filter(isRealDir)
        .map(toAbsolute(mount.mountpoint));

      while (check.length) {
        let path = check.pop();
        let stat = FS.stat(path);

        if (FS.isDir(stat.mode)) {
          check.push.apply(
            check,
            FS.readdir(path).filter(isRealDir).map(toAbsolute(path)),
          );
        }

        entries[path] = { timestamp: stat.mtime, mode: stat.mode };
      }

      return { type: "local", entries: entries };
    },
    // Returns file set of the real, on-disk filesystem at the mountpoint.
    getRemoteSet: async (mount: any) => {
      // TODO: this should be a map.
      const entries = Object.create(null);

      const handles = await getFsHandles(mount.opts.fileSystemHandle);
      for (const [path, handle] of handles) {
        if (path === ".") continue;

        entries[PATH.join2(mount.mountpoint, path)] = {
          timestamp:
            handle.kind === "file"
              ? new Date((await handle.getFile()).lastModified)
              : new Date(),
          mode:
            handle.kind === "file"
              ? nativeFSAsync.FILE_MODE
              : nativeFSAsync.DIR_MODE,
        };
      }

      return { type: "remote", entries, handles };
    },
    loadLocalEntry: (path: string) => {
      const lookup = FS.lookupPath(path, {});
      const node = lookup.node;
      const stat = FS.stat(path);

      if (FS.isDir(stat.mode)) {
        return { timestamp: stat.mtime, mode: stat.mode };
      } else if (FS.isFile(stat.mode)) {
        node.contents = MEMFS.getFileDataAsTypedArray(node);
        return {
          timestamp: stat.mtime,
          mode: stat.mode,
          contents: node.contents,
        };
      } else {
        throw new Error("node type not supported");
      }
    },
    storeLocalEntry: (path: string, entry: any) => {
      if (FS.isDir(entry["mode"])) {
        FS.mkdirTree(path, entry["mode"]);
      } else if (FS.isFile(entry["mode"])) {
        FS.writeFile(path, entry["contents"], { canOwn: true });
      } else {
        throw new Error("node type not supported");
      }

      FS.chmod(path, entry["mode"]);
      FS.utime(path, entry["timestamp"], entry["timestamp"]);
    },
    removeLocalEntry: (path: string) => {
      var stat = FS.stat(path);

      if (FS.isDir(stat.mode)) {
        FS.rmdir(path);
      } else if (FS.isFile(stat.mode)) {
        FS.unlink(path);
      }
    },
    loadRemoteEntry: async (handle: any) => {
      if (handle.kind === "file") {
        const file = await handle.getFile();
        return {
          contents: new Uint8Array(await file.arrayBuffer()),
          mode: nativeFSAsync.FILE_MODE,
          timestamp: new Date(file.lastModified),
        };
      } else if (handle.kind === "directory") {
        return {
          mode: nativeFSAsync.DIR_MODE,
          timestamp: new Date(),
        };
      } else {
        throw new Error("unknown kind: " + handle.kind);
      }
    },
    storeRemoteEntry: async (handles: any, path: string, entry: any) => {
      const parentDirHandle = handles.get(PATH.dirname(path));
      const handle = FS.isFile(entry.mode)
        ? await parentDirHandle.getFileHandle(PATH.basename(path), {
            create: true,
          })
        : await parentDirHandle.getDirectoryHandle(PATH.basename(path), {
            create: true,
          });
      if (handle.kind === "file") {
        const writable = await handle.createWritable();
        await writable.write(entry.contents);
        await writable.close();
      }
      handles.set(path, handle);
    },
    removeRemoteEntry: async (handles: any, path: string) => {
      const parentDirHandle = handles.get(PATH.dirname(path));
      await parentDirHandle.removeEntry(PATH.basename(path));
      handles.delete(path);
    },
    reconcile: async (mount: any, src: any, dst: any) => {
      let total = 0;

      const create: Array<string> = [];
      Object.keys(src.entries).forEach(function (key) {
        const e = src.entries[key];
        const e2 = dst.entries[key];
        if (
          !e2 ||
          (FS.isFile(e.mode) &&
            e["timestamp"].getTime() > e2["timestamp"].getTime())
        ) {
          create.push(key);
          total++;
        }
      });
      // sort paths in ascending order so directory entries are created
      // before the files inside them
      create.sort();

      const remove: Array<string> = [];
      Object.keys(dst.entries).forEach(function (key) {
        if (!src.entries[key]) {
          remove.push(key);
          total++;
        }
      });
      // sort paths in descending order so files are deleted before their
      // parent directories
      remove.sort().reverse();

      if (!total) {
        return;
      }

      const handles = src.type === "remote" ? src.handles : dst.handles;

      for (const path of create) {
        const relPath = PATH.normalize(
          path.replace(mount.mountpoint, "/"),
        ).substring(1);
        if (dst.type === "local") {
          const handle = handles.get(relPath);
          const entry = await nativeFSAsync.loadRemoteEntry(handle);
          nativeFSAsync.storeLocalEntry(path, entry);
        } else {
          const entry = nativeFSAsync.loadLocalEntry(path);
          await nativeFSAsync.storeRemoteEntry(handles, relPath, entry);
        }
      }

      for (const path of remove) {
        if (dst.type === "local") {
          nativeFSAsync.removeLocalEntry(path);
        } else {
          const relPath = PATH.normalize(
            path.replace(mount.mountpoint, "/"),
          ).substring(1);
          await nativeFSAsync.removeRemoteEntry(handles, relPath);
        }
      }
    },
  };

  module.FS.filesystems.NATIVEFS_ASYNC = nativeFSAsync;
}

const getFsHandles = async (dirHandle: any) => {
  const handles: any = [];

  async function collect(curDirHandle: any) {
    for await (const entry of curDirHandle.values()) {
      handles.push(entry);
      if (entry.kind === "directory") {
        await collect(entry);
      }
    }
  }

  await collect(dirHandle);

  const result = new Map();
  result.set(".", dirHandle);
  for (const handle of handles) {
    const relativePath = (await dirHandle.resolve(handle)).join("/");
    result.set(relativePath, handle);
  }
  return result;
};
