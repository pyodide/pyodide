/**
 * NodeSockFS — Node.js native socket filesystem replacing Emscripten's SOCKFS.
 * Uses WinterCG Sockets API as transport.
 *
 * This is used in two contexts:
 *   - Replacing socket syscalls: JSPI syscalls (socket_syscalls.c) — sync Python (socket.connect/recv/send)
 *     suspends the WASM stack via WebAssembly.Suspending, awaits the async op,
 *     resumes.
 *   - In asyncio webloop (webloop.py) - async Python event loop socket functions
 *     go through NodeSockFS directly.
 */

import {
  init as initWinterCGSockets,
  connect,
  Socket as WinterCGSocket,
} from "./wintercg-sockets";
import type { SocketOptions, ConnectFunc } from "./wintercg-sockets";
import type { FSStream, FSNode } from "../types";

interface NodeSock {
  family: number;
  type: number;
  protocol: number;
  error: number | null;
  /** The WinterCG Socket wrapping the underlying net.Socket / tls.TLSSocket */
  wcgSocket: WinterCGSocket | null;
  /** ReadableStream reader for receiving data */
  reader: ReadableStreamDefaultReader<Uint8Array> | null;
  /** WritableStream writer for sending data */
  writer: WritableStreamDefaultWriter<Uint8Array> | null;
  recvBuffer: Uint8Array[];
  recvBufferBytes: number;
  eof: boolean;
  dataAvailableResolve: (() => void) | null;
  pumpRunning: boolean;
  connected: boolean;
  connecting: boolean;
  closed: boolean;
  stream: FSStream;
  daddr?: string;
  dport?: number;
  saddr?: string;
  sport?: number;
  sock_ops: {
    poll: (sock: NodeSock) => number;
    ioctl: (sock: NodeSock, request: number) => number;
    close: (sock: NodeSock) => number;
    connectAsync: (
      sock: NodeSock,
      addr: string,
      port: number,
      options?: SocketOptions,
    ) => Promise<number>;
    sendmsgAsync: (sock: NodeSock, data: Uint8Array) => Promise<number>;
    recvmsgAsync: (
      sock: NodeSock,
      length: number,
    ) => Promise<Uint8Array | number>;
    bind: (sock: NodeSock, addr: string, port: number) => void;
    listen: (sock: NodeSock, backlog: number) => void;
    accept: (sock: NodeSock) => never;
  };
}

/**
 * Initialize NodeSockFS.
 * connectFunc can be optionally given to change the behavior of the connect function.
 * The conndctFunc should satisfy the WinterCG socket-api interface (https://github.com/WinterTC55/proposal-sockets-api),
 * and it is designed to be used in Cloudflare Workers
 */
export async function initializeNodeSockFS(
  connectFunc?: ConnectFunc,
): Promise<void> {
  if (!connectFunc) {
    await initWinterCGSockets();
    connectFunc = connect;
  }

  const module = Module;
  const FS = module.FS;
  const API = module.API;

  // following Emscripten's other FS implementations
  const DIR_MODE = cDefs.S_IFDIR | 0o777;

  // https://linux.die.net/man/2/shutdown
  const SHUT_RD = 0;
  const SHUT_WR = 1;
  const SHUT_RDWR = 2;

  function startRecvPump(sock: NodeSock): void {
    if (sock.pumpRunning || !sock.reader) return;
    sock.pumpRunning = true;
    (async () => {
      try {
        while (!sock.closed && sock.reader) {
          const { value, done } = await sock.reader.read();
          if (done || !value) {
            sock.eof = true;
            notifyDataAvailable(sock);
            break;
          }
          sock.recvBuffer.push(value);
          sock.recvBufferBytes += value.length;
          notifyDataAvailable(sock);
        }
      } catch {
        sock.eof = true;
        notifyDataAvailable(sock);
      } finally {
        sock.pumpRunning = false;
      }
    })();
  }

  function notifyDataAvailable(sock: NodeSock): void {
    if (sock.dataAvailableResolve) {
      const resolve = sock.dataAvailableResolve;
      sock.dataAvailableResolve = null;
      resolve();
    }
  }

  function waitForData(sock: NodeSock): Promise<void> {
    if (sock.recvBufferBytes > 0 || sock.eof || sock.closed) {
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      sock.dataAvailableResolve = resolve;
    });
  }

  function drainBuffer(sock: NodeSock, length: number): Uint8Array {
    if (
      sock.recvBuffer.length === 1 &&
      sock.recvBuffer[0].length <= length
    ) {
      const chunk = sock.recvBuffer.shift()!;
      sock.recvBufferBytes -= chunk.length;
      return chunk;
    }
    const out = new Uint8Array(Math.min(length, sock.recvBufferBytes));
    let offset = 0;
    while (offset < out.length && sock.recvBuffer.length > 0) {
      const chunk = sock.recvBuffer[0];
      const needed = out.length - offset;
      if (chunk.length <= needed) {
        out.set(chunk, offset);
        offset += chunk.length;
        sock.recvBuffer.shift();
      } else {
        out.set(chunk.subarray(0, needed), offset);
        sock.recvBuffer[0] = chunk.subarray(needed);
        offset += needed;
      }
    }
    sock.recvBufferBytes -= out.length;
    return out;
  }

  // Highly inspired by Emscripten's SOCKFS implementation
  // https://github.com/emscripten-core/emscripten/blob/main/src/lib/libsockfs.js
  const tcp_sock_ops = {
    poll(sock: NodeSock): number {
      let mask = 0;

      // Readable: we have buffered leftover data ready to return
      if (sock.recvBufferBytes > 0 || sock.eof) {
        mask |= cDefs.POLLRDNORM | cDefs.POLLIN;
      }

      // Writable: connected and writer is available
      if (sock.connected && sock.writer) {
        mask |= cDefs.POLLOUT;
      }

      // Hangup: the underlying transport has closed
      if (sock.closed) {
        mask |= cDefs.POLLHUP;
      }

      return mask;
    },

    /**
     * For now only FIONREAD is supported.
     * TODO: support other requests?
     */
    ioctl(sock: NodeSock, request: number): number {
      if (request === cDefs.FIONREAD) {
        return sock.recvBufferBytes;
      }
      return -cDefs.EINVAL;
    },

    /**
     * fnctl64 for NodeSock
     * Emscripten's __syscall_fcntl64(F_SETFL) does not handle cleaning up the
     * flags with F_SETFL properly, so we need to do it here.
     * TODO: Upstream this fix to Emscripten
     *
     * Other commands are fallbacked to emscripten's implementation.
     * (see socket_syscalls.c)
     */
    fcntl64(sock: NodeSock, cmd: number, varargs: number): number {
      if (cmd === cDefs.F_GETFL) {
        return sock.stream.flags;
      }
      if (cmd === cDefs.F_SETFL) {
        sock.stream.flags = module.HEAP32[varargs / 4];
        return 0;
      }
      return -cDefs.EINVAL;
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
      sock.recvBuffer = [];
      sock.recvBufferBytes = 0;
      notifyDataAvailable(sock);
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
        return -cDefs.EISCONN;
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

      try {
        await wcgSocket.opened;
        sock.connected = true;
        sock.connecting = false;
        sock.reader =
          wcgSocket.readable.getReader() as ReadableStreamDefaultReader<Uint8Array>;
        sock.writer =
          wcgSocket.writable.getWriter() as WritableStreamDefaultWriter<Uint8Array>;
        startRecvPump(sock);
        // Track when the underlying transport closes.
        // Swallow any errors while closing sockets.
        wcgSocket.closed.then(
          () => {
            sock.closed = true;
          },
          () => {
            sock.closed = true;
          },
        );
        return 0;
      } catch (err: unknown) {
        sock.error = cDefs.ECONNREFUSED;
        sock.connecting = false;
        return -sock.error;
      }
    },

    // Node.js support synchronous sendmsg while the wintercg sockets API is
    // asynchronous.
    async sendmsgAsync(sock: NodeSock, data: Uint8Array): Promise<number> {
      if (!sock.writer) {
        return -cDefs.ENOTCONN;
      }

      try {
        await sock.writer.write(data);
        return data.length;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("EPIPE") || msg.includes("ECONNRESET")) {
          return -cDefs.EPIPE;
        }
        return -cDefs.EIO;
      }
    },

    async recvmsgAsync(
      sock: NodeSock,
      length: number,
    ): Promise<Uint8Array | number> {
      if (sock.recvBufferBytes > 0) {
        return drainBuffer(sock, length);
      }

      if (sock.eof) {
        return 0;
      }

      if (sock.stream.flags & cDefs.O_NONBLOCK) {
        return -cDefs.EAGAIN;
      }

      await waitForData(sock);
      if (sock.recvBufferBytes > 0) {
        return drainBuffer(sock, length);
      }
      if (sock.eof) {
        return 0;
      }
      return -cDefs.EAGAIN;
    },

    shutdown(sock: NodeSock, how: number): number {
      if (how !== SHUT_RD && how !== SHUT_WR && how !== SHUT_RDWR) {
        return -cDefs.EINVAL;
      }

      if (how === SHUT_RD || how === SHUT_RDWR) {
        if (sock.reader) {
          sock.reader.releaseLock();
          sock.reader = null;
          sock.recvBuffer = [];
          sock.recvBufferBytes = 0;
          sock.eof = true;
          notifyDataAvailable(sock);
        }
      }

      if (how === SHUT_WR || how === SHUT_RDWR) {
        if (sock.writer) {
          sock.writer.releaseLock();
          sock.writer = null;
        }
      }

      if (sock.reader === null && sock.writer === null && sock.wcgSocket) {
        sock.wcgSocket.close().catch(() => {});
        sock.wcgSocket = null;
        sock.connected = false;
        sock.closed = true;
      }

      return 0;
    },

    /**
     * Start TLS on an existing socket.
     */
    startTls(sock: NodeSock): number {
      if (!sock.wcgSocket) {
        return -cDefs.ENOTCONN;
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
      sock.recvBuffer = [];
      sock.recvBufferBytes = 0;
      sock.eof = false;
      sock.pumpRunning = false;
      startRecvPump(sock);

      tlsSocket.closed.then(
        () => {
          sock.closed = true;
        },
        () => {
          sock.closed = true;
        },
      );
      return 0;
    },

    /*
     *  Server socket operations: not supported
     */

    bind(_sock: NodeSock, _addr: string, _port: number): void {
      throw new FS.ErrnoError(cDefs.EOPNOTSUPP);
    },

    listen(_sock: NodeSock, _backlog: number): void {
      throw new FS.ErrnoError(cDefs.EOPNOTSUPP);
    },

    accept(_sock: NodeSock): never {
      throw new FS.ErrnoError(cDefs.EOPNOTSUPP);
    },
  };

  const stream_ops = {
    poll(stream: FSStream): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.poll(sock);
    },

    ioctl(stream: FSStream, request: number): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.ioctl(sock, request);
    },

    write(): number {
      // All sends go through __syscall_sendto → sendmsgAsync.
      throw new FS.ErrnoError(cDefs.EOPNOTSUPP);
    },

    close(stream: FSStream): void {
      const sock = stream.node.sock as NodeSock;
      tcp_sock_ops.close(sock);
    },
  };

  // Counter for unique socket names
  let socketCounter = 0;

  // The main NodeSockFS object that will be mounted
  const NodeSockFS = {
    // Root node, set after mount
    root: null as FSNode | null,

    /**
     * Mount the filesystem
     */
    mount(): FSNode {
      return FS.createNode(null, "/", DIR_MODE, 0);
    },

    /**
     * Create a new socket.
     * This function replaces the original SOCKFS.createSocket.
     */
    createSocket(family: number, type: number, protocol: number): NodeSock {
      // Validate family - only AF_INET supported
      if (family !== cDefs.AF_INET) {
        throw new FS.ErrnoError(cDefs.EAFNOSUPPORT);
      }

      // Some applications may pass it; it makes no sense for a single process.
      // https://github.com/emscripten-core/emscripten/blob/af01558779231dcf3524438e904b688a5576432c/src/lib/libsockfs.js#L51C66-L51C139
      type &= ~(cDefs.SOCK_CLOEXEC | cDefs.SOCK_NONBLOCK);

      // Validate type - only SOCK_STREAM supported for now
      if (type !== cDefs.SOCK_STREAM) {
        if (type === cDefs.SOCK_DGRAM) {
          throw new FS.ErrnoError(cDefs.EOPNOTSUPP); // UDP not implemented
        }
        throw new FS.ErrnoError(cDefs.EINVAL);
      }

      // Validate protocol for TCP
      if (protocol && protocol !== cDefs.IPPROTO_TCP) {
        throw new FS.ErrnoError(cDefs.EPROTONOSUPPORT);
      }

      // create our internal socket structure
      // @ts-ignore (`stream` field is assigned later in this function)
      const sock: NodeSock = {
        family,
        type,
        protocol,
        error: null,
        wcgSocket: null,
        reader: null,
        writer: null,
        recvBuffer: [],
        recvBufferBytes: 0,
        eof: false,
        dataAvailableResolve: null,
        pumpRunning: false,
        connected: false,
        connecting: false,
        closed: false,
        sock_ops: tcp_sock_ops,
      };

      // create the filesystem node to store the socket structure
      const name = `socket[${socketCounter++}]`;
      const node = FS.createNode(NodeSockFS.root, name, cDefs.S_IFSOCK, 0);
      node.sock = sock;

      // and the wrapping stream that enables library functions such
      // as read and write to indirectly interact with the socket
      const stream = FS.createStream({
        path: name,
        node,
        flags: cDefs.O_RDWR,
        seekable: false,
        stream_ops,
      });

      // map the new stream to the socket structure (sockets have a 1:1
      // relationship with a stream)
      sock.stream = stream as FSStream;

      return sock;
    },

    /**
     * Get a socket by file descriptor
     */
    getSocket(fd: number): NodeSock | null {
      const stream = FS.getStream(fd) as FSStream;
      if (!stream || !FS.isSocket(stream.node.mode)) {
        return null;
      }
      return stream.node.sock as NodeSock;
    },
  };

  // Used in webloop.py to forward eventloop socket operations to Node.js
  API._nodeSock = {
    async connect(fd: number, host: string, port: number): Promise<void> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(cDefs.EBADF);
      }
      const result = await tcp_sock_ops.connectAsync(sock, host, port);
      if (result < 0) {
        throw new FS.ErrnoError(-result);
      }
    },

    async recv(fd: number, nbytes: number): Promise<Uint8Array> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(cDefs.EBADF);
      }
      while (sock.recvBufferBytes === 0 && !sock.eof && !sock.closed) {
        await waitForData(sock);
      }
      if (sock.recvBufferBytes > 0) {
        return drainBuffer(sock, nbytes);
      }
      return new Uint8Array(0);
    },

    async send(
      fd: number,
      data: Uint8Array | any /* or PyProxy of bytes object */,
    ): Promise<number> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        throw new FS.ErrnoError(cDefs.EBADF);
      }
      let buf: Uint8Array;
      if (data instanceof Uint8Array) {
        buf = data;
      } else if (data.toJs) {
        buf = data.toJs();
      } else {
        buf = new Uint8Array(data);
      }
      return await tcp_sock_ops.sendmsgAsync(sock, buf);
    },

    startTls(fd: number): number {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        return -cDefs.EBADF;
      }
      return tcp_sock_ops.startTls(sock);
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
}
