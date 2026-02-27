/**
 * NodeSockFS — Node.js native socket filesystem replacing Emscripten's SOCKFS.
 * Uses WinterCG Sockets API as transport.
 *
 * JSPI syscalls (socket_syscalls.c) — sync Python (socket.connect/recv/send)
 * suspends the WASM stack via WebAssembly.Suspending, awaits the async op,
 * resumes.
 */

import type { PyodideModule, PreRunFunc } from "../types";
import { RUNTIME_ENV } from "../environments";
import {
  init as initWinterCGSockets,
  connect,
  Socket as WinterCGSocket,
} from "./wintercg-sockets";
import type { SocketOptions } from "./wintercg-sockets";

interface NodeSock {
  family: number;
  type: number;
  protocol: number;
  server: any;
  error: number | null;
  /** The WinterCG Socket wrapping the underlying net.Socket / tls.TLSSocket */
  wcgSocket: WinterCGSocket | null;
  /** ReadableStream reader for receiving data */
  reader: ReadableStreamDefaultReader<Uint8Array> | null;
  /** WritableStream writer for sending data */
  writer: WritableStreamDefaultWriter<Uint8Array> | null;
  /** Leftover bytes from a previous read that were larger than requested */
  leftover: Uint8Array | null;
  connected: boolean;
  connecting: boolean;
  closed: boolean;
  stream?: any;
  daddr?: string;
  dport?: number;
  saddr?: string;
  sport?: number;
  sock_ops: any;
}

export function initializeNodeSockFS(): PreRunFunc[] {
  if (!RUNTIME_ENV.IN_NODE) {
    throw new Error("NodeSockFS is only supported in Node.js");
  }

  return [
    async (module: PyodideModule) => {
      module.addRunDependency("initializeNodeSockFSHook");
      try {
        await _initializeNodeSockFS(module);
      } finally {
        module.removeRunDependency("initializeNodeSockFSHook");
      }
    },
  ];
}

async function _initializeNodeSockFS(module: PyodideModule) {
  await initWinterCGSockets();

  const FS = module.FS;
  const ERRNO_CODES = module.ERRNO_CODES;

  // Values copied from Emscripten
  const AF_INET = 2;
  const SOCK_STREAM = 1;
  const SOCK_DGRAM = 2;
  const SOCK_CLOEXEC = 0o2000000;
  const SOCK_NONBLOCK = 0o4000;
  const IPPROTO_TCP = 6;
  const S_IFSOCK = 0o140000;
  const O_RDWR = 0o2;
  const DIR_MODE = 16384 | 0o777;

  const POLLIN = 0x001;
  const POLLOUT = 0x004;
  const POLLHUP = 0x010;
  const POLLRDNORM = 0x040;

  const FIONREAD = 0x541b;

  // Highly inspired by Emscripten's SOCKFS implementation
  // https://github.com/emscripten-core/emscripten/blob/main/src/lib/libsockfs.js
  const tcp_sock_ops = {
    poll(sock: NodeSock): number {
      let mask = 0;

      // Readable: we have buffered leftover data ready to return
      if (sock.leftover && sock.leftover.length > 0) {
        mask |= POLLRDNORM | POLLIN;
      }

      // Writable: connected and writer is available
      if (sock.connected && sock.writer) {
        mask |= POLLOUT;
      }

      // Hangup: the underlying transport has closed
      if (sock.closed) {
        mask |= POLLHUP;
      }

      return mask;
    },

    /**
     * For now only FIONREAD is supported.
     * TODO: support other requests?
     */
    ioctl(sock: NodeSock, request: number, _arg: any): number {
      if (request === FIONREAD) {
        return sock.leftover ? sock.leftover.length : 0;
      }
      return 0;
    },

    close(sock: NodeSock): number {
      if (sock.wcgSocket) {
        if (sock.reader) {
          sock.reader.releaseLock();
          sock.reader = null;
        }
        if (sock.writer) {
          sock.writer.releaseLock();
          sock.writer = null;
        }
        sock.wcgSocket.close().catch(() => {});
        sock.wcgSocket = null;
      }
      sock.leftover = null;
      sock.connected = false;
      sock.connecting = false;
      sock.closed = true;
      return 0;
    },

    async connectAsync(
      sock: NodeSock,
      addr: string,
      port: number,
      options?: SocketOptions,
    ): Promise<number> {
      if (sock.wcgSocket) {
        return -ERRNO_CODES.EISCONN;
      }

      sock.connecting = true;
      sock.daddr = addr;
      sock.dport = port;

      const wcgSocket = connect(
        { hostname: addr, port },
        {
          secureTransport: options?.secureTransport ?? "off",
          allowHalfOpen: false,
        },
      );

      sock.wcgSocket = wcgSocket;

      try {
        await wcgSocket.opened;
        sock.connected = true;
        sock.connecting = false;
        sock.reader =
          wcgSocket.readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
        sock.writer =
          wcgSocket.writable.getWriter() as WritableStreamDefaultWriter<Uint8Array>;
        // Track when the underlying transport closes
        wcgSocket.closed
          .then(() => {
            sock.closed = true;
          })
          .catch(() => {
            sock.closed = true;
          });
        return 0;
      } catch (err: unknown) {
        sock.error = ERRNO_CODES.ECONNREFUSED;
        sock.connecting = false;
        return -sock.error;
      }
    },

    async sendmsgAsync(sock: NodeSock, data: Uint8Array): Promise<number> {
      if (!sock.writer) {
        return -ERRNO_CODES.ENOTCONN;
      }

      try {
        await sock.writer.write(data);
        return data.length;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("EPIPE") || msg.includes("ECONNRESET")) {
          return -ERRNO_CODES.EPIPE;
        }
        return -ERRNO_CODES.EIO;
      }
    },

    async recvmsgAsync(
      sock: NodeSock,
      length: number,
    ): Promise<Uint8Array | null> {
      if (sock.leftover && sock.leftover.length > 0) {
        const bytesRead = Math.min(length, sock.leftover.length);
        const result = sock.leftover.subarray(0, bytesRead);
        sock.leftover =
          bytesRead < sock.leftover.length
            ? sock.leftover.subarray(bytesRead)
            : null;
        return result;
      }

      if (!sock.reader) {
        return null;
      }

      try {
        const { value, done } = await sock.reader.read();
        if (done || !value) {
          return null;
        }

        if (value.length <= length) {
          return value;
        }

        sock.leftover = value.subarray(length);
        return value.subarray(0, length);
      } catch {
        return null;
      }
    },

    /*
     *  Server socket operations: not supported
     */

    bind(_sock: NodeSock, _addr: string, _port: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    listen(_sock: NodeSock, _backlog: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    accept(_sock: NodeSock): never {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },
  };

  const stream_ops = {
    poll(stream: any): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.poll(sock);
    },

    ioctl(stream: any, request: number, varargs: any): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.ioctl(sock, request, varargs);
    },

    write(): number {
      // All sends go through __syscall_sendto → sendmsgAsync.
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    close(stream: any): void {
      const sock = stream.node.sock as NodeSock;
      tcp_sock_ops.close(sock);
    },
  };

  // Counter for unique socket names
  let socketCounter = 0;

  // The main NodeSockFS object that will be mounted
  const NodeSockFS: any = {
    // Root node, set after mount
    root: null as any,

    /**
     * Mount the filesystem
     */
    mount(_mount: any): any {
      return FS.createNode(null, "/", DIR_MODE, 0);
    },

    /**
     * Create a new socket.
     * This function replaces the original SOCKFS.createSocket.
     */
    createSocket(family: number, type: number, protocol: number): NodeSock {
      // Validate family - only AF_INET supported
      if (family !== AF_INET) {
        throw new FS.ErrnoError(ERRNO_CODES.EAFNOSUPPORT);
      }

      // Some applications may pass it; it makes no sense for a single process.
      //github.com/emscripten-core/emscripten/blob/af01558779231dcf3524438e904b688a5576432c/src/lib/libsockfs.js#L51C66-L51C139
      https: type &= ~(SOCK_CLOEXEC | SOCK_NONBLOCK);

      // Validate type - only SOCK_STREAM supported for now
      if (type !== SOCK_STREAM) {
        if (type === SOCK_DGRAM) {
          throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP); // UDP not implemented
        }
        throw new FS.ErrnoError(ERRNO_CODES.EINVAL);
      }

      // Validate protocol for TCP
      if (protocol && protocol !== IPPROTO_TCP) {
        throw new FS.ErrnoError(ERRNO_CODES.EPROTONOSUPPORT);
      }

      // create our internal socket structure
      const sock: NodeSock = {
        family,
        type,
        protocol,
        server: null,
        error: null,
        wcgSocket: null,
        reader: null,
        writer: null,
        leftover: null,
        connected: false,
        connecting: false,
        closed: false,
        sock_ops: tcp_sock_ops,
      };

      // create the filesystem node to store the socket structure
      const name = `socket[${socketCounter++}]`;
      const node = FS.createNode(NodeSockFS.root, name, S_IFSOCK, 0);
      node.sock = sock;

      // and the wrapping stream that enables library functions such
      // as read and write to indirectly interact with the socket
      const stream = FS.createStream({
        path: name,
        node,
        flags: O_RDWR,
        seekable: false,
        stream_ops,
      });

      // map the new stream to the socket structure (sockets have a 1:1
      // relationship with a stream)
      sock.stream = stream;

      return sock;
    },
  };

  module.FS.filesystems.NODESOCKFS = NodeSockFS;

  // @ts-ignore - Use `pseudo` mountpoint which is null. It is not documented but used in Emscripten code
  NodeSockFS.root = module.FS.mount(NodeSockFS, {}, null);

  // Replace the SOCKFS APIs with NodeSockFS
  // This makes the syscall layer use our implementation
  // FIXME: This depends on internal Emscripten structures, which may change anytime.
  //        We should consider contributing upstream or finding a more stable integration method.
  module.SOCKFS.createSocket = NodeSockFS.createSocket;

  return NodeSockFS;
}
