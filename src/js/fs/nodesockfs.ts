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
import { sleep } from "../scheduler";
import {
  createResolvable,
  type ResolvablePromise,
} from "../common/resolveable";

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

  /**
   * Buffer for received data
   * In nonblocking mode, this buffer is used to store data that has been received
   * but not yet read by the application.
   */
  recvBuffer: Uint8Array[];
  recvBufferBytes: number;
  /**
   * The stream has reached FIN.
   * It does not mean the stream is closed, but it will not receive any more data.
   */
  eof: boolean;
  /**
   * Promise that resolves when data is available
   * Used in blocking mode to suspend the WASM stack until data is available.
   */
  dataAvailable: ResolvablePromise | null;

  /** A read() call is in flight on the current ReadableStream reader. */
  readPending: boolean;
  /** Resolves when the current read() call settles. */
  readSettled: Promise<void> | null;

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
    pollAsync: (
      sock: NodeSock,
      events: number,
      timeout: number,
    ) => Promise<number>;
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
    startTls: (sock: NodeSock) => Promise<number>;
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

  // see struct_info_generated.json
  const POLLFD_FD = 0;
  const POLLFD_EVENTS = 4;
  const POLLFD_REVENTS = 6;
  const POLLFD_SIZE = 8;

  /**
   * Start a single receive from the underlying ReadableStream.
   * Reads are started by recv()/poll() demand.
   */
  function startRead(sock: NodeSock): void {
    const reader = sock.reader;
    // Not gated on sock.closed: a peer close leaves the reader intact with data
    // and a FIN still to drain, so reads continue until the stream reports done
    // (eof). A local close nulls sock.reader, which the `!reader` guard stops.
    if (sock.readPending || sock.eof || !reader) {
      return;
    }
    sock.readPending = true;

    const readSettled = (async () => {
      try {
        let result: ReadableStreamReadResult<Uint8Array>;
        try {
          result = await reader.read();
        } catch {
          // The reader was released (e.g. startTls swapped it) or errored.
          if (sock.reader === reader) {
            sock.eof = true;
            notifyDataAvailable(sock);
          }
          return;
        }

        // A reader swap can only happen across the await above.
        if (sock.reader !== reader) return;
        if (result.done) {
          sock.eof = true;
          notifyDataAvailable(sock);
          return;
        }

        sock.recvBuffer.push(result.value);
        sock.recvBufferBytes += result.value.length;
        notifyDataAvailable(sock);
      } finally {
        sock.readPending = false;
      }
    })();
    sock.readSettled = readSettled;
    // Clean up the readSettled promise when it completes
    readSettled.finally(() => {
      if (sock.readSettled === readSettled) {
        sock.readSettled = null;
      }
    });
  }

  function notifyDataAvailable(sock: NodeSock): void {
    if (sock.dataAvailable) {
      sock.dataAvailable.resolve();
      sock.dataAvailable = null;
    }
  }

  /**
   * Block until data is available to read or the socket is closed.
   */
  function waitForData(sock: NodeSock): Promise<void> {
    if (sock.recvBufferBytes > 0 || sock.eof) {
      return Promise.resolve();
    }
    if (!sock.reader) {
      return Promise.resolve();
    }
    sock.dataAvailable ??= createResolvable();
    startRead(sock);
    return sock.dataAvailable;
  }

  function drainBuffer(sock: NodeSock, length: number): Uint8Array {
    if (sock.recvBufferBytes === 0) {
      return new Uint8Array(0);
    }

    // Enough data in a single chunk
    if (sock.recvBuffer.length === 1 && sock.recvBuffer[0].length <= length) {
      const chunk = sock.recvBuffer.shift()!;
      sock.recvBufferBytes = 0;
      return chunk;
    }

    // If not enough data in a single chunk, concatenate chunks
    // until we have enough or run out of data
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

      // Readable: buffered data is ready, or EOF can be observed.
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

    async pollAsync(
      sock: NodeSock,
      events: number,
      timeout: number,
    ): Promise<number> {
      // Get the events that are currently ready
      // https://github.com/emscripten-core/emscripten/blob/61533b1fbd7fefc1792220aa0499db1724471e74/src/lib/libsyscall.js#L599
      const getRequestedEvents = (): number =>
        tcp_sock_ops.poll(sock) & (events | cDefs.POLLERR | cDefs.POLLHUP);

      const ready = getRequestedEvents();
      // timeout == 0: No wait, return immediately
      if (ready || timeout === 0) return ready;

      // timeout < 0: Infinite wait
      if (timeout < 0) {
        // wait for data to become available
        await waitForData(sock);
      } else {
        // timeout > 0: Wait for the specified time
        // Race between waiting for data and the timeout
        await Promise.race([waitForData(sock), sleep(timeout)]);
      }
      return getRequestedEvents();
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
      // Signal any pending read to stop before touching the reader.
      sock.closed = true;
      notifyDataAvailable(sock);

      if (sock.wcgSocket) {
        sock.reader = null;
        sock.writer = null;
        sock.wcgSocket.close().catch(() => {});
        sock.wcgSocket = null;
      }
      sock.recvBuffer = [];
      sock.recvBufferBytes = 0;
      sock.connected = false;
      sock.connecting = false;
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
      const tryDrain = (): Uint8Array | number | null => {
        const data = drainBuffer(sock, length);
        if (data.length > 0) return data;
        if (sock.eof) return 0;
        return null;
      };

      const ready = tryDrain();
      if (ready !== null) return ready;

      if (sock.stream.flags & cDefs.O_NONBLOCK) {
        // Kick a demand read so the buffer can fill for a later poll/retry, then
        // report EAGAIN when nothing is buffered yet, as a nonblocking recv must.
        startRead(sock);
        return tryDrain() ?? -cDefs.EAGAIN;
      }

      while (sock.recvBufferBytes === 0 && !sock.eof && sock.reader) {
        await waitForData(sock);
      }
      return tryDrain() ?? -cDefs.EAGAIN;
    },

    shutdown(sock: NodeSock, how: number): number {
      if (how !== SHUT_RD && how !== SHUT_WR && how !== SHUT_RDWR) {
        return -cDefs.EINVAL;
      }

      if (how === SHUT_RD || how === SHUT_RDWR) {
        if (sock.reader) {
          sock.reader = null;
          sock.recvBuffer = [];
          sock.recvBufferBytes = 0;
          sock.eof = true;
          notifyDataAvailable(sock);
        }
      }

      if (how === SHUT_WR || how === SHUT_RDWR) {
        if (sock.writer) {
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
    async startTls(sock: NodeSock): Promise<number> {
      if (!sock.wcgSocket) {
        return -cDefs.ENOTCONN;
      }
      // Releasing a ReadableStream reader while read() is pending throws in
      // workerd. Since Web Streams do not provide a non-destructive way to
      // interrupt that read, wait for it to settle before releasing the lock.
      while (sock.readPending && sock.readSettled) {
        await sock.readSettled;
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
      tlsSocket.closed.then(
        () => {
          sock.closed = true;
        },
        () => {
          sock.closed = true;
        },
      );
      startRead(sock);
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
        dataAvailable: null,
        readPending: false,
        readSettled: null,
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

    /**
     * poll syscall for NodeSock fds
     * The implementation is mostly adopted from
     * - https://github.com/emscripten-core/emscripten/blob/main/src/lib/libsyscall.js
     * - https://github.com/python/cpython/blob/main/Python/emscripten_syscalls.c
     */
    async pollAsync(
      fds: number,
      nfds: number,
      timeout: number,
    ): Promise<number> {
      let count = 0;
      const waits: Promise<void>[] = [];
      for (let i = 0; i < nfds; i++) {
        const pollfd = fds + POLLFD_SIZE * i;
        const fd = module.HEAP32[(pollfd + POLLFD_FD) >> 2];
        const events = module.HEAP16[(pollfd + POLLFD_EVENTS) >> 1];
        const setRevents = (flags: number): void => {
          flags &= events | cDefs.POLLERR | cDefs.POLLHUP;
          module.HEAP16[(pollfd + POLLFD_REVENTS) >> 1] = flags;
          if (flags) {
            count++;
          }
        };

        const sock = NodeSockFS.getSocket(fd);
        if (!sock) {
          // stream not found
          setRevents(cDefs.POLLNVAL);
        } else if (timeout === 0) {
          setRevents(sock.sock_ops.poll(sock));
        } else {
          waits.push(
            sock.sock_ops.pollAsync(sock, events, timeout).then(setRevents),
          );
        }
      }
      await Promise.all(waits);
      return count;
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
      while (sock.recvBufferBytes === 0 && !sock.eof && sock.reader) {
        await waitForData(sock);
      }
      return drainBuffer(sock, nbytes);
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

    async startTls(fd: number): Promise<number> {
      const sock = NodeSockFS.getSocket(fd);
      if (!sock) {
        return -cDefs.EBADF;
      }
      return await tcp_sock_ops.startTls(sock);
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
  module.SOCKFS.pollAsync = NodeSockFS.pollAsync;
}
