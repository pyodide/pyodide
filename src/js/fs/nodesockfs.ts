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

import type { PyodideModule, PreRunFunc, FSType, API } from "../types";
import { RUNTIME_ENV } from "../environments";
import { setPyodideModuleforJSPI } from "../emscripten-settings";
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
  /** Leftover bytes from a previous read that were larger than requested */
  leftover: Uint8Array | null;
  connected: boolean;
  connecting: boolean;
  /** Whether the socket has been upgraded to TLS */
  tls: boolean;
  stream?: any;
  daddr?: string;
  dport?: number;
  saddr?: string;
  sport?: number;
  sock_ops: any;
}

export function initializeNodeSockFS(): PreRunFunc[] {
  if (!RUNTIME_ENV.IN_NODE) {
    DEBUG &&
      console.debug(
        "[NodeSockFS] Not in Node.js environment, skipping NodeSockFS initialization",
      );
    return [];
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
  const FS = module.FS;
  const api = module.API;
  const ERRNO_CODES = module.ERRNO_CODES;

  setPyodideModuleforJSPI(module);

  await initWinterCGSockets();

  DEBUG && console.debug(`[NodeSockFS] Initializing...`);
  DEBUG &&
    console.debug(
      `[NodeSockFS] Module.jspiSupported: ${(module as any).jspiSupported}`,
    );

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

      if (
        (sock.leftover && sock.leftover.length > 0) ||
        (sock.wcgSocket?.innerSocket?.readableLength ?? 0) > 0
      ) {
        mask |= POLLRDNORM | POLLIN;
      }

      const innerSocket = sock.wcgSocket?.innerSocket;
      if (sock.connected && innerSocket && !innerSocket.destroyed) {
        mask |= POLLOUT;
      }

      if (innerSocket?.destroyed) {
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
        sock.wcgSocket.close().catch(() => {});
        sock.wcgSocket = null;
      }
      sock.leftover = null;
      sock.connected = false;
      sock.connecting = false;
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

      const wcgSocket = connect(
        { hostname: addr, port },
        {
          secureTransport: options?.secureTransport ?? "off",
          allowHalfOpen: true,
        },
      );

      sock.wcgSocket = wcgSocket;
      sock.tls = options?.secureTransport === "on";

      return wcgSocket.opened
        .then(() => {
          sock.connected = true;
          sock.connecting = false;
          sock.reader =
            wcgSocket.readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
          DEBUG &&
            console.debug(`[NodeSockFS:connectAsync] Connection established`);
          return 0;
        })
        .catch((err: unknown) => {
          sock.error = ERRNO_CODES.ECONNREFUSED;
          sock.connecting = false;
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

    sendmsg(
      sock: NodeSock,
      buffer: Uint8Array,
      offset: number,
      length: number,
      _addr?: string,
      _port?: number,
    ): number {
      DEBUG && console.debug(`[NodeSockFS:sendmsg] length=${length}`);

      if (!sock.wcgSocket) {
        throw new FS.ErrnoError(ERRNO_CODES.ENOTCONN);
      }

      const data = buffer.subarray(offset, offset + length);
      sock.wcgSocket.innerSocket.write(data);
      return length;
    },

    recvmsgAsync(
      sock: NodeSock,
      length: number,
    ): Promise<{ bytesRead: number; buffer: Uint8Array } | null> {
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
        return Promise.resolve({ bytesRead, buffer: new Uint8Array(data) });
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
            return { bytesRead: chunk.length, buffer: new Uint8Array(chunk) };
          }

          sock.leftover = chunk.subarray(length);
          return {
            bytesRead: length,
            buffer: new Uint8Array(chunk.subarray(0, length)),
          };
        },
        () => null,
      );
    },

    async upgradeTLSAsync(
      sock: NodeSock,
      options?: {
        servername?: string;
        rejectUnauthorized?: boolean;
        ca?: string;
        cert?: string;
        key?: string;
      },
    ): Promise<number> {
      DEBUG &&
        console.debug(
          `[NodeSockFS:upgradeTLSAsync] servername=${options?.servername}`,
        );

      if (!sock.wcgSocket) {
        return -ERRNO_CODES.ENOTCONN;
      }
      if (sock.tls) {
        return -ERRNO_CODES.EISCONN;
      }

      try {
        // Guard against data loss: leftover bytes from TCP phase must be
        // consumed before upgrading to TLS, since the TLS handshake replaces
        // the readable stream entirely.
        if (sock.leftover && sock.leftover.length > 0) {
          console.warn(
            `[NodeSockFS:upgradeTLSAsync] ${sock.leftover.length} leftover bytes will be lost during TLS upgrade`,
          );
        }

        if (sock.reader) {
          sock.reader.releaseLock();
          sock.reader = null;
        }

        const tls = await import("node:tls");
        const tlsSocket = tls.connect({
          socket: sock.wcgSocket.innerSocket,
          servername: options?.servername,
          rejectUnauthorized: options?.rejectUnauthorized ?? true,
          ca: options?.ca,
          cert: options?.cert,
          key: options?.key,
        });

        await new Promise<void>((resolve, reject) => {
          const onSecure = () => {
            cleanup();
            resolve();
          };
          const onError = (err: Error) => {
            cleanup();
            reject(err);
          };
          const cleanup = () => {
            tlsSocket.off("secureConnect", onSecure);
            tlsSocket.off("error", onError);
          };
          tlsSocket.once("secureConnect", onSecure);
          tlsSocket.once("error", onError);
        });

        const { Duplex } = await import("node:stream");
        const { readable } = (Duplex as any).toWeb(tlsSocket) as {
          readable: ReadableStream<Uint8Array>;
        };

        (sock.wcgSocket as any)._socket = tlsSocket;
        (sock.wcgSocket as any).readable = readable;

        sock.reader =
          readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
        sock.tls = true;
        sock.leftover = null;

        DEBUG && console.debug(`[NodeSockFS:upgradeTLSAsync] Complete`);
        return 0;
      } catch (err: unknown) {
        DEBUG &&
          console.debug(
            `[NodeSockFS:upgradeTLSAsync] Error: ${err instanceof Error ? err.message : err}`,
          );
        return -ERRNO_CODES.ECONNREFUSED;
      }
    },

    getname(sock: NodeSock, peer: boolean): { addr: string; port: number } {
      if (peer) {
        if (!sock.daddr || !sock.dport) {
          throw new FS.ErrnoError(ERRNO_CODES.ENOTCONN);
        }
        return { addr: sock.daddr, port: sock.dport };
      } else {
        return { addr: sock.saddr || "0.0.0.0", port: sock.sport || 0 };
      }
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

    write(
      stream: any,
      buffer: Uint8Array,
      offset: number,
      length: number,
      _position: any,
    ): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.sendmsg(sock, buffer, offset, length);
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
        leftover: null,
        connected: false,
        connecting: false,
        tls: false,
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

  module.FS.filesystems.NODESOCKFS = NodeSockFS;

  // @ts-ignore - Use `pseudo` mountpoint which is null. It is not documented but used in Emscripten code
  NodeSockFS.root = module.FS.mount(NodeSockFS, {}, null);

  // Replace the SOCKFS APIs with NodeSockFS
  // This makes the syscall layer use our implementation
  // FIXME: This depends on internal Emscripten structures, which may change anytime.
  //        We should consider contributing upstream or finding a more stable integration method.
  module.SOCKFS.createSocket = NodeSockFS.createSocket;
  module.SOCKFS.getSocket = NodeSockFS.getSocket;

  return NodeSockFS;
}
