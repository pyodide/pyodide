/**
 * NodeSockFS - A Node.js native socket filesystem for Emscripten/Pyodide
 *
 * This replaces Emscripten's WebSocket-based SOCKFS with native Node.js sockets.
 * Currently implements TCP client sockets only (SOCK_STREAM + connect).
 */

import type { PyodideModule } from "../types";
import type { Socket } from "node:net";
import { RUNTIME_ENV } from "../environments"; 

// Internal socket structure that mirrors Emscripten's sock structure
interface NodeSock {
  family: number;
  type: number;
  protocol: number;
  server: any;
  error: number | null;
  nodeSocket: Socket | null;
  recvBuffer: Buffer; // Buffer for incoming data
  connected: boolean; // Connection state
  connecting: boolean; // Whether connect is in progress
  stream?: any; // The FS stream
  daddr?: string; // Destination address
  dport?: number; // Destination port
  saddr?: string; // Source address (for bind)
  sport?: number; // Source port (for bind)
  sock_ops: any; // Socket operations
}

export async function initializeNodeSockFS(module: PyodideModule) {
  if (!RUNTIME_ENV.IN_NODE) {
    return;
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
  const FS: any = module.FS;
  const ERRNO_CODES: any = module.ERRNO_CODES;

  // Import Node.js modules
  const net = await import("node:net");

  // Constants matching Emscripten/POSIX definitions
  const AF_INET = 2;
  const SOCK_STREAM = 1;
  const SOCK_DGRAM = 2;
  const SOCK_CLOEXEC = 0o2000000;
  const SOCK_NONBLOCK = 0o4000;
  const IPPROTO_TCP = 6;
  const S_IFSOCK = 0o140000;
  const O_RDWR = 0o2;
  const DIR_MODE = 16384 | 0o777;

  // Poll event flags
  const POLLIN = 0x001;
  const POLLOUT = 0x004;
  const POLLHUP = 0x010;
  const POLLRDNORM = 0x040;

  // Socket operations - these are called via sock.sock_ops.method(sock, ...) inside the libsyscall
  const tcp_sock_ops = {
    /**
     * Poll the socket for readability/writability
     */
    poll(sock: NodeSock): number {
      let mask = 0;

      // Check if there's data to read
      if (sock.recvBuffer.length > 0) {
        mask |= POLLRDNORM | POLLIN;
      }

      // Check if socket is writable (connected and not destroyed)
      if (sock.connected && sock.nodeSocket && !sock.nodeSocket.destroyed) {
        mask |= POLLOUT;
      }

      // Check if socket is closed/closing
      if (sock.nodeSocket?.destroyed) {
        mask |= POLLHUP;
      }

      return mask;
    },

    /**
     * Handle ioctl calls
     */
    ioctl(sock: NodeSock, request: number, _arg: any): number {
      // FIONREAD (0x541B) - return number of bytes available to read
      const FIONREAD = 0x541b;
      if (request === FIONREAD) {
        // Would need to write to arg, but for now just return 0
        return 0;
      }
      return 0;
    },

    /**
     * Close the socket
     */
    close(sock: NodeSock): number {
      if (sock.nodeSocket) {
        sock.nodeSocket.destroy();
        sock.nodeSocket = null;
      }
      sock.connected = false;
      sock.connecting = false;
      return 0;
    },

    /**
     * Bind socket to address/port (not implemented for client-only PoC)
     */
    bind(_sock: NodeSock, _addr: string, _port: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    /**
     * Connect to a remote address
     */
    connect(sock: NodeSock, addr: string, port: number): void {
      if (sock.nodeSocket) {
        throw new FS.ErrnoError(ERRNO_CODES.EISCONN);
      }

      // Create new TCP socket
      const socket = new net.Socket();
      sock.nodeSocket = socket;
      sock.connecting = true;
      sock.daddr = addr;
      sock.dport = port;

      // Handle incoming data
      socket.on("data", (data: Buffer) => {
        // Append to receive buffer
        sock.recvBuffer = Buffer.concat([sock.recvBuffer, data]);
      });

      // Handle connection established
      socket.on("connect", () => {
        sock.connected = true;
        sock.connecting = false;
      });

      // Handle errors
      socket.on("error", (_err: NodeJS.ErrnoException) => {
        sock.error = ERRNO_CODES.ECONNREFUSED;
        sock.connecting = false;
      });

      // Handle close
      socket.on("close", () => {
        sock.connected = false;
        sock.connecting = false;
      });

      // Initiate connection (non-blocking in Node.js)
      socket.connect(port, addr);
    },

    /**
     * Listen for connections (not implemented for client-only PoC)
     */
    listen(_sock: NodeSock, _backlog: number): void {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    /**
     * Accept a connection (not implemented for client-only PoC)
     */
    accept(_sock: NodeSock): never {
      throw new FS.ErrnoError(ERRNO_CODES.EOPNOTSUPP);
    },

    /**
     * Send data through the socket
     */
    sendmsg(
      sock: NodeSock,
      buffer: Uint8Array,
      offset: number,
      length: number,
      _addr?: string,
      _port?: number,
    ): number {
      if (!sock.nodeSocket) {
        throw new FS.ErrnoError(ERRNO_CODES.ENOTCONN);
      }

      // For TCP, we ignore addr/port as the socket is already connected
      const data = buffer.subarray(offset, offset + length);

      // Write to the socket
      // Note: Node.js write is async, but we return immediately like the original SOCKFS
      sock.nodeSocket.write(data);

      return length;
    },

    /**
     * Receive data from the socket
     */
    recvmsg(sock: NodeSock, length: number): { buffer: Uint8Array } | null {
      // If no data available
      if (sock.recvBuffer.length === 0) {
        // If socket is closed, return null to signal EOF
        if (!sock.nodeSocket || sock.nodeSocket.destroyed) {
          return null;
        }
        // Otherwise, would block (EAGAIN) - but stream_ops.read handles this
        // by returning 0 when recvmsg returns null
        return null;
      }

      // Read requested amount (or less if not enough data)
      const bytesRead = Math.min(length, sock.recvBuffer.length);
      const data = new Uint8Array(sock.recvBuffer.subarray(0, bytesRead));

      // Remove read data from buffer
      sock.recvBuffer = sock.recvBuffer.subarray(bytesRead);

      return { buffer: data };
    },

    /**
     * Get socket name info (for getsockname/getpeername)
     */
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

  // Stream operations - these are called via stream.stream_ops.method(stream, ...)
  const stream_ops = {
    poll(stream: any): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.poll(sock);
    },

    ioctl(stream: any, request: number, varargs: any): number {
      const sock = stream.node.sock as NodeSock;
      return tcp_sock_ops.ioctl(sock, request, varargs);
    },

    read(
      stream: any,
      buffer: Uint8Array,
      offset: number,
      length: number,
      _position: any,
    ): number {
      const sock = stream.node.sock as NodeSock;
      const msg = tcp_sock_ops.recvmsg(sock, length);
      if (!msg) {
        // No data available or socket closed
        return 0;
      }
      buffer.set(msg.buffer, offset);
      return msg.buffer.length;
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
        throw new FS.ErrnoError(ERRNO_CODES.EAFNOSUPPORT);
      }

      // Strip CLOEXEC and NONBLOCK flags
      type &= ~(SOCK_CLOEXEC | SOCK_NONBLOCK);

      // Validate type - only SOCK_STREAM supported in this PoC
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

      // Create internal socket structure
      const sock: NodeSock = {
        family,
        type,
        protocol,
        server: null,
        error: null,
        nodeSocket: null,
        recvBuffer: Buffer.alloc(0),
        connected: false,
        connecting: false,
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
      if (!stream || !FS.isSocket(stream.node.mode)) {
        return null;
      }
      return stream.node.sock as NodeSock;
    },
  };

  // Mount the filesystem and store root
  NodeSockFS.root = FS.mount(NodeSockFS, {}, null);

  // Replace the global SOCKFS with our implementation
  // This makes the syscall layer use our implementation
  (module as any).SOCKFS = NodeSockFS;

  return NodeSockFS;
}
