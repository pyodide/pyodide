/**
 * NodeSockFS — Node.js native socket filesystem replacing Emscripten's SOCKFS.
 * Uses WinterCG Sockets API as transport.
 *
 * Two I/O paths exist:
 *  1. JSPI syscalls (emscripten-settings.ts) — sync Python (socket.connect/recv/send)
 *     suspends the WASM stack via WebAssembly.Suspending, awaits the async op, resumes.
 *  2. api._nodeSock helpers (below) — asyncio Python (WebLoop.sock_connect/recv/sendall)
 *     calls these directly as JS Promises without WASM suspension, avoiding thread
 *     state corruption inside the event loop.
 */

import type { API } from "../types";
import {
  init as initWinterCGSockets,
  connect,
  Socket as WinterCGSocket,
} from "./wintercg-sockets";
import type { SocketOptions, ConnectFunc } from "./wintercg-sockets";

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

export async function initializeNodeSockFS(connectFunc?: ConnectFunc) {
  if (!connectFunc) {
    await initWinterCGSockets();
    connectFunc = connect;
  }

  const FS = Module.FS;
  const api = Module.API;
  const ERRNO_CODES = Module.ERRNO_CODES;

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

  const tcp_sock_ops = {
    poll(sock: NodeSock): number {
      let mask = 0;

      if (sock.leftover && sock.leftover.length > 0) {
        mask |= POLLRDNORM | POLLIN;
      }

      if (sock.connected && sock.writer) {
        mask |= POLLOUT;
      }

      if (sock.closed) {
        mask |= POLLHUP;
      }

      return mask;
    },

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

    bind(_sock: NodeSock, _addr: string, _port: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    connectAsync(
      sock: NodeSock,
      addr: string,
      port: number,
      options?: SocketOptions,
    ): Promise<number> {
      DEBUG &&
        console.debug(
          `[NodeSockFS:connectAsync] addr=${addr}, port=${port}, tls=${options?.secureTransport ?? "off"}`,
        );

      if (sock.wcgSocket) {
        return Promise.resolve(-ERRNO_CODES.EISCONN);
      }

      sock.connecting = true;
      sock.daddr = addr;
      sock.dport = port;

      const wcgSocket = connectFunc(
        { hostname: addr, port },
        {
          secureTransport: options?.secureTransport ?? "starttls",
          allowHalfOpen: false,
        },
      );

      sock.wcgSocket = wcgSocket;

      return wcgSocket.opened
        .then(() => {
          sock.connected = true;
          sock.connecting = false;
          sock.closed = false;
          sock.reader =
            wcgSocket.readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
          sock.writer =
            wcgSocket.writable.getWriter() as WritableStreamDefaultWriter<Uint8Array>;
          wcgSocket.closed
            .then(() => {
              sock.closed = true;
            })
            .catch(() => {
              sock.closed = true;
            });
          DEBUG &&
            console.debug(`[NodeSockFS:connectAsync] Connection established`);
          return 0;
        })
        .catch((err: unknown) => {
          sock.error = ERRNO_CODES.ECONNREFUSED;
          sock.connecting = false;
          sock.closed = true;
          DEBUG &&
            console.debug(
              `[NodeSockFS:connectAsync] Error: ${err instanceof Error ? err.message : err}`,
            );
          return -ERRNO_CODES.ECONNREFUSED;
        });
    },

    listen(_sock: NodeSock, _backlog: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    accept(_sock: NodeSock): never {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    startTls(sock: NodeSock): number {
      if (!sock.wcgSocket) {
        return -ERRNO_CODES.ENOTCONN;
      }

      if (sock.reader) {
        sock.reader.releaseLock();
        sock.reader = null;
      }
      if (sock.writer) {
        sock.writer.releaseLock();
        sock.writer = null;
      }

      const tlsSocket = sock.wcgSocket.startTls();

      sock.wcgSocket = tlsSocket;
      sock.reader =
        tlsSocket.readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
      sock.writer =
        tlsSocket.writable.getWriter() as WritableStreamDefaultWriter<Uint8Array>;
      sock.leftover = null;

      tlsSocket.closed
        .then(() => {
          sock.closed = true;
        })
        .catch(() => {
          sock.closed = true;
        });

      return 0;
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

    recvmsgAsync(sock: NodeSock, length: number): Promise<Uint8Array | null> {
      DEBUG && console.debug(`[NodeSockFS:recvmsgAsync] requested=${length}`);

      if (sock.leftover && sock.leftover.length > 0) {
        const bytesRead = Math.min(length, sock.leftover.length);
        const data = sock.leftover.subarray(0, bytesRead);
        sock.leftover =
          bytesRead < sock.leftover.length
            ? sock.leftover.subarray(bytesRead)
            : null;
        DEBUG &&
          console.debug(
            `[NodeSockFS:recvmsgAsync] ${bytesRead} bytes from leftover`,
          );
        return Promise.resolve(new Uint8Array(data));
      }

      if (!sock.reader) {
        return Promise.resolve(null);
      }

      return sock.reader.read().then(
        ({ value, done }) => {
          if (done || !value) {
            DEBUG && console.debug(`[NodeSockFS:recvmsgAsync] EOF`);
            return null;
          }

          const chunk =
            value instanceof Uint8Array ? value : new Uint8Array(value as any);

          if (chunk.length <= length) {
            return new Uint8Array(chunk);
          }

          sock.leftover = chunk.subarray(length);
          return new Uint8Array(chunk.subarray(0, length));
        },
        () => null,
      );
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
     * Create a new socket
     */
    createSocket(family: number, type: number, protocol: number): NodeSock {
      // Validate family - only AF_INET supported
      if (family !== AF_INET) {
        DEBUG && console.debug(`[NodeSockFS] Unsupported family: ${family}`);
        throw new FS.ErrnoError(ERRNO_CODES.EAFNOSUPPORT);
      }

      // Strip CLOEXEC and NONBLOCK flags
      type &= ~(SOCK_CLOEXEC | SOCK_NONBLOCK);

      // Validate type - only SOCK_STREAM supported in this PoC
      if (type !== SOCK_STREAM) {
        if (type === SOCK_DGRAM) {
          DEBUG && console.debug("[NodeSockFS] UDP sockets not implemented");
          throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP); // UDP not implemented
        }
        DEBUG && console.debug(`[NodeSockFS] Unsupported socket type: ${type}`);
        throw new FS.ErrnoError(ERRNO_CODES.EINVAL);
      }

      // Validate protocol for TCP
      if (protocol && protocol !== IPPROTO_TCP) {
        DEBUG &&
          console.debug(`[NodeSockFS] Unsupported protocol: ${protocol}`);
        throw new FS.ErrnoError(ERRNO_CODES.EPROTONOSUPPORT);
      }

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

      // Create filesystem node
      const name = `socket[${socketCounter++}]`;
      const node = FS.createNode(NodeSockFS.root, name, S_IFSOCK, 0);
      node.sock = sock;

      // Create stream for the socket
      const stream = FS.createStream({
        path: name,
        node,
        flags: O_RDWR,
        seekable: false,
        stream_ops,
      });

      // Link socket to stream
      sock.stream = stream;

      return sock;
    },

    /**
     * Get a socket by file descriptor
     */
    getSocket(fd: number): NodeSock | null {
      const stream = FS.getStream(fd);
      if (!stream || !FS.isSocket((stream as any).node.mode)) {
        return null;
      }
      return (stream as any).node.sock as NodeSock;
    },
  };

  Module.FS.filesystems.NODESOCKFS = NodeSockFS;

  // @ts-ignore - Use `pseudo` mountpoint which is null. It is not documented but used in Emscripten code
  NodeSockFS.root = Module.FS.mount(NodeSockFS, {}, null);

  Module.SOCKFS.createSocket = NodeSockFS.createSocket;
  Module.SOCKFS.getSocket = NodeSockFS.getSocket;

  (api as any)._nodeSock = {
    async connect(fd: number, host: string, port: number): Promise<void> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(ERRNO_CODES.EBADF);
      }
      const result = await tcp_sock_ops.connectAsync(sock, host, port);
      if (result < 0) {
        throw new FS.ErrnoError(-result);
      }
    },

    async recv(fd: number, nbytes: number): Promise<Uint8Array> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(ERRNO_CODES.EBADF);
      }
      const result = await tcp_sock_ops.recvmsgAsync(sock, nbytes);
      if (result === null) {
        return new Uint8Array(0);
      }
      return result;
    },

    async send(fd: number, data: any): Promise<number> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(ERRNO_CODES.EBADF);
      }
      let buf: Uint8Array;
      if (data instanceof Uint8Array) {
        buf = data;
      } else if (data.toJs) {
        buf = data.toJs();
        data.destroy();
      } else {
        buf = new Uint8Array(data);
      }
      return await tcp_sock_ops.sendmsgAsync(sock, buf);
    },

    async connectTLS(fd: number, host: string, port: number): Promise<void> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(ERRNO_CODES.EBADF);
      }
      const result = await tcp_sock_ops.connectAsync(sock, host, port, {
        secureTransport: "on",
      });
      if (result < 0) {
        throw new FS.ErrnoError(-result);
      }
    },

    startTls(fd: number): number {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        return -ERRNO_CODES.EBADF;
      }
      return tcp_sock_ops.startTls(sock);
    },
  };

  return NodeSockFS;
}
