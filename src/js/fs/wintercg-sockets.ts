/**
 * WinterCG Sockets API — Node.js implementation of the TC39/WinterCG `connect()` proposal.
 *
 * Adapted from @arrowood.dev/socket (https://github.com/Ethan-Arrowood/socket)
 * Original author: Ethan Arrowood <ethan@arrowood.dev>
 * License: MIT
 *
 * Modifications for Pyodide:
 *   - Dynamic `import('node:net')` / `import('node:tls')` to avoid top-level
 *     Node.js dependencies (keeps the module importable in browser builds).
 *   - Merged types.ts and is-socket-address.ts into a single file.
 *   - Merged types.ts and is-socket-address.ts into a single file.
 *   - Module-level `init()` must be called once before `connect()`.
 */

import type { Duplex } from "node:stream";
import type { ReadableStream, WritableStream } from "node:stream/web";

export interface SocketOptions {
  /**
   * Specifies whether or not to use TLS when creating the TCP socket.
   * `off` — Do not use TLS.
   * `on` — Use TLS.
   * `starttls` — Do not use TLS initially, but allow the socket to be
   *   upgraded to use TLS by calling startTls().
   */
  secureTransport?: "off" | "on" | "starttls";
  /**
   * Defines whether the writable side of the TCP socket will automatically
   * close on end-of-file (EOF).
   */
  allowHalfOpen?: boolean;
}

export interface SocketAddress {
  /** The hostname to connect to. Example: `cloudflare.com`. */
  hostname: string;
  /** The port number to connect to. Example: `5432`. */
  port: number;
}

export interface SocketInfo {
  remoteAddress?: string;
  localAddress?: string;
}

function isSocketAddress(address: unknown): address is SocketAddress {
  return (
    typeof address === "object" &&
    address !== null &&
    Object.hasOwn(address, "hostname") &&
    Object.hasOwn(address, "port")
  );
}

let _net: typeof import("node:net") | null = null;
let _tls: typeof import("node:tls") | null = null;
let _duplexToWeb:
  | ((duplex: Duplex) => {
      readable: ReadableStream<unknown>;
      writable: WritableStream<unknown>;
    })
  | null = null;

/**
 * Must be called once before using `connect()`.  Dynamically loads `node:net`,
 * `node:tls`, and `node:stream` so that this module has no top-level Node.js
 * dependencies.
 */
export async function init(): Promise<void> {
  if (_net) return; // already initialised
  const [net, tls, stream] = await Promise.all([
    import("node:net"),
    import("node:tls"),
    import("node:stream"),
  ]);
  _net = net;
  _tls = tls;
  // Duplex.toWeb types are wrong in @types/node — cast through unknown.
  _duplexToWeb = (duplex: Duplex) =>
    (stream.Duplex as any).toWeb(duplex) as {
      readable: ReadableStream<unknown>;
      writable: WritableStream<unknown>;
    };
}

function getNet(): typeof import("node:net") {
  if (!_net) throw new Error("wintercg-sockets: call init() first");
  return _net;
}

function getTls(): typeof import("node:tls") {
  if (!_tls) throw new Error("wintercg-sockets: call init() first");
  return _tls;
}

function getDuplexToWeb() {
  if (!_duplexToWeb) throw new Error("wintercg-sockets: call init() first");
  return _duplexToWeb;
}

export class SocketError extends TypeError {
  constructor(message: string) {
    super(`SocketError: ${message}`);
  }
}

export function connect(
  address: SocketAddress | string,
  options?: SocketOptions,
): Socket {
  if (typeof address === "string") {
    const url = new URL(`https://${address}`);
    address = {
      hostname: url.hostname,
      port: parseInt(url.port === "" ? "443" : url.port),
    };
  }
  return new Socket(address, options);
}

export class Socket {
  readable: ReadableStream<unknown>;
  writable: WritableStream<unknown>;
  opened: Promise<SocketInfo>;
  closed: Promise<void>;

  private _socket: import("node:net").Socket | import("node:tls").TLSSocket;
  private allowHalfOpen: boolean;
  private secureTransport: SocketOptions["secureTransport"];
  private openedIsResolved: boolean;
  private openedResolve!: (info: SocketInfo) => void;
  private openedReject!: (reason?: unknown) => void;
  private closedResolve!: () => void;
  private closedReject!: (reason?: unknown) => void;
  private startTlsCalled = false;



  constructor(
    addressOrSocket: SocketAddress | import("node:net").Socket,
    options?: SocketOptions,
  ) {
    const net = getNet();
    const tls = getTls();
    const duplexToWeb = getDuplexToWeb();

    this.secureTransport = options?.secureTransport ?? "off";
    this.allowHalfOpen = options?.allowHalfOpen ?? true;

    this.openedIsResolved = false;
    this.opened = new Promise((resolve, reject) => {
      this.openedResolve = (info): void => {
        this.openedIsResolved = true;
        resolve(info);
      };
      this.openedReject = (...args): void => {
        this.openedIsResolved = true;
        reject(...args);
      };
    });

    this.closed = new Promise((resolve, reject) => {
      this.closedResolve = (...args): void => {
        resolve(...args);
      };
      this.closedReject = (...args): void => {
        reject(...args);
      };
    });

    if (isSocketAddress(addressOrSocket)) {
      const connectOptions: import("node:net").NetConnectOpts = {
        host: addressOrSocket.hostname,
        port: addressOrSocket.port,
        allowHalfOpen: this.allowHalfOpen,
      };
      if (this.secureTransport === "on") {
        this._socket = tls.connect(connectOptions);
      } else {
        this._socket = net.connect(connectOptions);
      }
    } else {
      this._socket = new tls.TLSSocket(addressOrSocket);
    }

    if (this._socket instanceof tls.TLSSocket) {
      this._socket.on("secureConnect", () => {
        this.openedResolve({
          remoteAddress: this._socket.remoteAddress,
          localAddress: this._socket.localAddress,
        });
      });
    } else {
      this._socket.on("connect", () => {
        this.openedResolve({
          remoteAddress: this._socket.remoteAddress,
          localAddress: this._socket.localAddress,
        });
      });
    }

    this._socket.on("close", (hadError: boolean) => {
      if (!hadError) {
        this.closedResolve();
      }
    });

    this._socket.on("error", (err: Error) => {
      const socketError = new SocketError(
        err instanceof Error ? err.message : (err as unknown as string),
      );
      if (!this.openedIsResolved) {
        this.openedReject(socketError);
      }
      this.closedReject(socketError);
    });

    const { readable, writable } = duplexToWeb(
      this._socket as unknown as Duplex,
    );
    this.readable = readable;
    this.writable = writable;
  }

  close(): Promise<void> {
    this._socket.end(() => {
      this.closedResolve();
    });
    return this.closed;
  }

  startTls(): Socket {
    if (this.secureTransport !== "starttls") {
      throw new SocketError("secureTransport must be set to 'starttls'");
    }
    if (this.startTlsCalled) {
      throw new SocketError("can only call startTls once");
    } else {
      this.startTlsCalled = true;
    }

    return new Socket(this._socket as import("node:net").Socket, {
      secureTransport: "on",
    });
  }
}
