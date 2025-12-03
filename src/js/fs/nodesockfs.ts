
import { PyodideModule, FSStream } from "../types";
import type { Socket } from 'net';

export async function initializeNodeSockFS(module: PyodideModule) {
  const FS = module.FS;
  const ERROR_CODES = module.ERRNO_CODES;

  const dgram = await import("node:dgram");
  const net = await import("node:net");

  function tcpStreamOps(sock: Socket) {
    const _sock = sock;

    let recvBuffer = Buffer.alloc(0);
    
    _sock.on('data', (data: Buffer) => {
      // append incoming chunk to temporary receive buffer
      // @ts-ignore
      let _recvBuffer = Buffer.concat([recvBuffer, data]);
      // expose buffer on the socket for other ops to read
      recvBuffer = _recvBuffer;
    });


    return {
      // poll(sock: any) {
      //   return 0;
      // },
      ioctl(sock: any, request: number, arg: any) {
        return 0;
      },
      close(sock: any) {
        // not in node:types for some reason I don't understand
        // @ts-ignore
        _sock.destroy();
      },
      bind(sock: any, addr: any, port: any) {
        // TODO: Implement bind logic
        throw new FS.ErrnoError(ERROR_CODES.EINVAL);
      },
      connect(sock: any, addr: any, port: any) {
        _sock.connect(port, addr);
      },
      listen(sock: any, backlog: number) {
        // TODO: Implement server listen logic
        throw new FS.ErrnoError(ERROR_CODES.EINVAL);
      },
      accept(listensock: any) {
        // TODO: Implement server accept logic
        throw new FS.ErrnoError(ERROR_CODES.EINVAL);
      },
      sendmsg(sock: any, buffer: Uint8Array, offset: number, length: number, addr?: any, port?: any) {
        // TODO: avoid copying
        // @ts-ignore
        _sock.write(buffer.subarray(offset, offset + length));
        return length;
      },
      recvmsg(sock: any, length: number) {
        if (recvBuffer.length === 0) {
          return null;
        }
        const bytesRead = Math.min(length, recvBuffer.length);
        const res = {
          buffer: new Uint8Array(recvBuffer.buffer, recvBuffer.byteOffset, bytesRead),
        };
        // remove read data from the buffer
        recvBuffer = recvBuffer.slice(bytesRead);
        return res;
      },
    }
  }

  const nodeSockFS = {
    current: 0,
    
    DIR_MODE: 16384 | 0o777,
    AF_INET: 2,
    SOCK_CLOEXEC: 0o2000000,
    SOCK_NONBLOCK: 0o4000,
    SOCK_STREAM: 1,
    SOCK_DGRAM: 2,
    IPPROTO_TCP: 6,
    S_IFSOCK: 0o140000,
    O_RDWR: 0o2,

    mount: function (mount: any) {
      return FS.createNode(null, '/', nodeSockFS.DIR_MODE, 0);
    },

    createSocket: function(family: number, type: number, protocol: number) {
      // Emscripten only supports AF_INET
      if (family != nodeSockFS.AF_INET) {
        throw new FS.ErrnoError(ERROR_CODES.EAFNOSUPPORT);
      }
      type &= ~ (nodeSockFS.SOCK_CLOEXEC | nodeSockFS.SOCK_NONBLOCK); // Some applications may pass it; it makes no sense for a single process.
      // Emscripten only supports SOCK_STREAM and SOCK_DGRAM
      if (type != nodeSockFS.SOCK_STREAM && type != nodeSockFS.SOCK_DGRAM) {
        throw new FS.ErrnoError(ERROR_CODES.EINVAL);
      }
      var streaming = type == nodeSockFS.SOCK_STREAM;
      if (streaming && protocol && protocol != nodeSockFS.IPPROTO_TCP) {
        throw new FS.ErrnoError(ERROR_CODES.EPROTONOSUPPORT); // if SOCK_STREAM, must be tcp or 0.
      }

      // create our internal socket structure
      var sock = {
        family,
        type,
        protocol,
        server: null,
        error: null, // Used in getsockopt for SOL_SOCKET/SO_ERROR test
        peers: {},
        pending: [],
        recv_queue: [],
        sock_ops: nodeSockFS.sock_ops
      };

      // create the filesystem node to store the socket structure
      var name = nodeSockFS.nextname();
      var node = FS.createNode(nodeSockFS.root, name, nodeSockFS.S_IFSOCK, 0);
      node.sock = sock;

      // and the wrapping stream that enables library functions such
      // as read and write to indirectly interact with the socket
      // @ts-ignore
      var stream = FS.createStream({
        path: name,
        node,
        flags: nodeSockFS.O_RDWR,
        seekable: false,
        stream_ops: nodeSockFS.stream_ops
      });

      // map the new stream to the socket structure (sockets have a 1:1
      // relationship with a stream)
      sock.stream = stream;

      return sock;
    },

    getSocket: function(fd: number) {
      var stream = FS.getStream(fd);
      if (!stream || !FS.isSocket(stream.node.mode)) {
        return null;
      }
      return stream.node.sock;
    },

    // node and stream ops are backend agnostic
    stream_ops: {
      // poll(stream: FSStream) {
      //   var sock = stream.node.sock;
      //   return sock.sock_ops.poll(sock);
      // },
      ioctl(stream: FSStream, request: number, varargs: any) {
        var sock = stream.node.sock;
        return sock.sock_ops.ioctl(sock, request, varargs);
      },
      read(stream: FSStream, buffer: Uint8Array, offset: number, length: number, position: any /* ignored */) {
        var sock = stream.node.sock;
        var msg = sock.sock_ops.recvmsg(sock, length);
        if (!msg) {
          // socket is closed
          return 0;
        }
        buffer.set(msg.buffer, offset);
        return msg.buffer.length;
      },
      write(stream: FSStream, buffer: Uint8Array, offset: number, length: number, position: any /* ignored */) {
        var sock = stream.node.sock;
        return sock.sock_ops.sendmsg(sock, buffer, offset, length);
      },
      close(stream: FSStream) {
        var sock = stream.node.sock;
        sock.sock_ops.close(sock);
      }
    },
    nextname: function(): string {
      if (!nodeSockFS.nextname.current) {
        nodeSockFS.nextname.current = 0;
      }
      return `socket[${nodeSockFS.nextname.current++}]`;
    },
    
    // backend-specific stream ops
    sock_ops: tcpStreamOps(),
  };
};
