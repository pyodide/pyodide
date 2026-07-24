import { PyodideModule } from "./types";

// https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle
interface FileSystemSyncAccessHandle {
  close(): void;
  flush(): void;
  getSize(): number;
  read(buffer: ArrayBufferView, options?: { at?: number }): number;
  write(buffer: ArrayBufferView, options?: { at?: number }): number;
  truncate(newSize: number): void;
}

interface OPFSFileHandle extends FileSystemFileHandle {
  createSyncAccessHandle(): Promise<FileSystemSyncAccessHandle>;
}

export function initializeOPFS(module: PyodideModule) {
  const FS = module.FS;
  const MEMFS = module.FS.filesystems.MEMFS;
  const PATH = module.PATH;

  const syncHandles = new Map<number, FileSystemSyncAccessHandle>();

  // node_ops for OPFS-backed files. We reuse MEMFS for everything except the
  // size-related attributes, which must be read from the live OPFS sync handle
  // rather than from the (empty) MEMFS buffer. Without this, fstat reports a
  // size of 0, so os.path.getsize() returns 0 and any size-aware read (e.g.
  // pathlib.read_text(), which preallocates st_size bytes) yields empty data.
  const node_ops = {
    getattr(node: any) {
      const attr = MEMFS.node_ops.getattr(node);
      const handle = syncHandles.get(node.id);
      if (handle) {
        attr.size = handle.getSize();
        attr.blocks = Math.ceil(attr.size / attr.blksize);
      }
      return attr;
    },
    setattr(node: any, attr: any) {
      const handle = syncHandles.get(node.id);
      if (handle && attr.size !== undefined) {
        // Route truncation to OPFS and strip size before delegating, so that
        // MEMFS does not allocate an in-memory buffer of the new size (which
        // would defeat the point of streaming directly from OPFS).
        handle.truncate(attr.size);
        attr = { ...attr };
        delete attr.size;
      }
      return MEMFS.node_ops.setattr(node, attr);
    },
  };

  const stream_ops = {
    open(stream: any) {
      if (FS.isFile(stream.node.mode) && !syncHandles.has(stream.node.id)) {
        throw new Error(`No sync handle for ${stream.node.name}`);
      }
    },
    read(
      stream: any,
      buffer: Uint8Array,
      offset: number,
      length: number,
      pos: number,
    ): number {
      const handle = syncHandles.get(stream.node.id)!;
      const slice = buffer.subarray(offset, offset + length);
      return handle.read(slice, { at: pos });
    },
    write(
      stream: any,
      buffer: Uint8Array,
      offset: number,
      length: number,
      pos: number,
    ): number {
      const handle = syncHandles.get(stream.node.id)!;
      const slice = buffer.subarray(offset, offset + length);
      return handle.write(slice, { at: pos });
    },
    close(stream: any) {
      const handle = syncHandles.get(stream.node.id);
      if (handle) {
        handle.flush();
      }
    },
    llseek(stream: any, offset: number, whence: number): number {
      const handle = syncHandles.get(stream.node.id)!;
      let pos;
      if (whence === 0)
        pos = offset; // SEEK_SET
      else if (whence === 1)
        pos = stream.position + offset; // SEEK_CUR
      else if (whence === 2)
        pos = handle.getSize() + offset; // SEEK_END
      else throw new Error("Invalid whence");
      if (pos < 0) throw new Error("Invalid position");
      return pos;
    },
    fsync(stream: any) {
      const handle = syncHandles.get(stream.node.id);
      if (handle) {
        handle.flush();
      }
    },
  };

  const opfsWorkerFS = {
    DIR_MODE: 16384 | 511,
    FILE_MODE: 32768 | 511,

    mount(mount: any) {
      if (!mount.opts.opfsHandle) {
        throw new Error("opts.opfsHandle is required");
      }
      return MEMFS.mount.apply(null, arguments as any);
    },
    node_ops,
    stream_ops,
  };

  async function loadOPFS(
    mountpoint: string,
    opfsHandle: FileSystemDirectoryHandle,
  ) {
    async function traverse(
      dirHandle: FileSystemDirectoryHandle,
      dirPath: string,
    ) {
      for await (const entry of (dirHandle as any).values()) {
        const entryPath = PATH.join2(dirPath, entry.name);
        if (entry.kind === "directory") {
          FS.mkdir(entryPath);
          await traverse(entry, entryPath);
        } else {
          FS.writeFile(entryPath, new Uint8Array());
          const node = FS.lookupPath(entryPath, {}).node as any;
          // Back this file by OPFS: size comes from the sync handle (node_ops)
          // and reads/writes go straight to OPFS (stream_ops).
          node.node_ops = node_ops;
          node.stream_ops = stream_ops;
          // TODO: Pre-creating sync handles at mount time is a workaround for the fact that
          // createSyncAccessHandle() is async and cannot be called inside synchronous
          // stream_ops.open(). This should be migrated to JSPI (WebAssembly JavaScript
          // Promise Integration) so that handles can be created lazily on open(),
          // enabling support for files created after mount.
          const handle = await (
            entry as OPFSFileHandle
          ).createSyncAccessHandle();
          syncHandles.set(node.id, handle);
        }
      }
    }

    await traverse(opfsHandle, mountpoint);
  }

  module.FS.filesystems.OPFS_WORKER_FS = opfsWorkerFS;
  module.API.loadOPFS = loadOPFS;
}
