import { RUNTIME_ENV } from "./environments.js";
import "./constants";

import type { FSStream, FSStreamOpsGen, TtyOps } from "./types";
const fs: typeof import("node:fs") = RUNTIME_ENV.IN_NODE
  ? require("node:fs")
  : undefined;
const tty: typeof import("node:tty") = RUNTIME_ENV.IN_NODE
  ? require("node:tty")
  : undefined;

function nodeFsync(fd: number): void {
  try {
    fs.fsyncSync(fd);
  } catch (e: any) {
    if (e?.code === "EINVAL") {
      return;
    }
    // On Mac, calling fsync when not isatty returns ENOTSUP
    // On Windows, stdin/stdout/stderr may be closed, returning EBADF or EPERM
    const isStdStream = fd === 0 || fd === 1 || fd === 2;
    if (
      isStdStream &&
      (e?.code === "ENOTSUP" || e?.code === "EBADF" || e?.code === "EPERM")
    ) {
      return;
    }

    throw e;
  }
}

type Reader = {
  isatty?: boolean;
  fsync?: () => void;
  read(buffer: Uint8Array): number;
};

/**
 * A Writer to provide to :js:func:`~pyodide.setStdout` or
 * :js:func:`~pyodide.setStderr`.
 *
 * ``Writer.write`` is called with a series of `Uint8Array` buffers containing
 * bytes to write to the stream.
 *
 * ``isatty`` controls whether `isatty()` returns `true` or `false` for the
 * stream. It defaults to `false`.
 *
 * If present, and `isatty` is `true`, `getTerminalSize()` controls the size of
 * the terminal reported by the tiocgwinsz ioctl, which propagates to
 * `os.get_terminal_size()`. If absent, the terminal size is reported as 24 rows
 * by 80 columns.
 *
 * If provided, `fsync` is called when the stream is fsync'd.
 */
export interface Writer {
  isatty?: boolean;
  fsync?: () => void;
  write(buffer: Uint8Array): number;
  getTerminalSize?: () => { rows: number; columns: number } | undefined;
}

type Stream = FSStream & {
  stream_ops: StreamOps;
  devops: Reader & Writer;
};

type StreamOps = FSStreamOpsGen<Stream>;

declare var FS: typeof Module.FS;

// The type of the function we expect the user to give us. make_get_char takes
// one of these and turns it into a GetCharType function for us.
/** @hidden */
export type InFuncType = () =>
  | null
  | undefined
  | string
  | ArrayBuffer
  | Uint8Array
  | number;

/**
 * We call refreshStreams at the end of every update method, but refreshStreams
 * won't work until initializeStreams is called. So when INITIALIZED is false,
 * refreshStreams is a no-op.
 * @private
 */
let INITIALIZED = false;
const DEVOPS: { [k: number]: Reader & Writer } = {};
// DEVS is initialized in initializeStreams
const DEVS = {} as {
  stdin: number;
  stdout: number;
  stderr: number;
};

function _setStdinOps(ops: Reader) {
  DEVOPS[DEVS.stdin] = ops as Reader & Writer;
}

function _setStdoutOps(ops: Writer) {
  DEVOPS[DEVS.stdout] = ops as Reader & Writer;
}

function _setStderrOps(ops: Writer) {
  DEVOPS[DEVS.stderr] = ops as Reader & Writer;
}

function isErrnoError(e: any) {
  return e && typeof e === "object" && "errno" in e;
}

const waitBuffer = new Int32Array(
  new WebAssembly.Memory({ shared: true, initial: 1, maximum: 1 }).buffer,
);
function syncSleep(timeout: number): boolean {
  try {
    Atomics.wait(waitBuffer, 0, 0, timeout);
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Calls the callback and handle node EAGAIN errors.
 *
 * In the long run, it may be helpful to allow C code to handle these errors on
 * their own, at least if the Emscripten file descriptor has O_NONBLOCK on it.
 * That way the code could do other periodic tasks in the delay loop.
 *
 * This code is outside of the stream handler itself so if the user wants to
 * inject some code in this loop they could do it with:
 * ```js
 * read(buffer) {
 *   try {
 *     return doTheRead();
 *   } catch(e) {
 *     if (e && e.code === "EAGAIN") {
 *       // do periodic tasks
 *     }
 *     // in every case rethrow the error
 *     throw e;
 *   }
 * }
 * ```
 */
function handleEAGAIN(cb: () => number): number {
  while (true) {
    try {
      return cb();
    } catch (e: any) {
      if (e && e.code === "EAGAIN") {
        // Presumably this means we're in node and tried to read from/write to
        // an O_NONBLOCK file descriptor. Synchronously sleep for 100ms as
        // requested by EAGAIN and try again. In case for some reason we fail to
        // sleep, propagate the error (it will turn into an EOFError).
        if (syncSleep(100)) {
          continue;
        }
      }
      throw e;
    }
  }
}

function readWriteHelper(stream: Stream, cb: () => number, method: string) {
  let nbytes;
  try {
    nbytes = handleEAGAIN(cb);
  } catch (e: any) {
    if (e && e.code && Module.ERRNO_CODES[e.code]) {
      throw new FS.ErrnoError(Module.ERRNO_CODES[e.code]);
    }
    if (isErrnoError(e)) {
      // the handler set an errno, propagate it
      throw e;
    }
    console.error(`Error thrown in ${method}:`);
    console.error(e);
    throw new FS.ErrnoError(cDefs.EIO);
  }
  if (nbytes === undefined) {
    // Prevent an infinite loop caused by incorrect code that doesn't return a
    // value
    // Maybe we should set nbytes = buffer.length here instead?
    console.warn(
      `${method} returned undefined; a correct implementation must return a number`,
    );
    throw new FS.ErrnoError(cDefs.EIO);
  }
  if (nbytes !== 0) {
    stream.node.timestamp = Date.now();
  }
  return nbytes;
}

const prepareBuffer = (
  buffer: Uint8Array,
  offset: number,
  length: number,
): Uint8Array =>
  API.typedArrayAsUint8Array(buffer).subarray(offset, offset + length);

type FSTty = {
  ops: TtyOps<FSTty>;
  devops: Reader & Writer;
};

const TTY_OPS = {
  ioctl_tiocgwinsz(tty: FSTty): readonly [number, number] {
    const { rows = 24, columns = 80 } = tty.devops.getTerminalSize?.() ?? {};
    return [rows, columns];
  },
};

const stream_ops: StreamOps = {
  open: function (stream) {
    const devops = DEVOPS[stream.node.rdev];
    if (!devops) {
      throw new FS.ErrnoError(cDefs.ENODEV);
    }
    stream.devops = devops;
    stream.tty = stream.devops.isatty
      ? {
          ops: TTY_OPS,
          devops,
        }
      : undefined;
    stream.seekable = false;
  },
  close: function (stream) {
    // flush any pending line data
    stream.stream_ops.fsync(stream);
  },
  fsync: function (stream) {
    const ops = stream.devops;
    if (ops.fsync) {
      ops.fsync();
    }
  },
  read: function (stream, buffer, offset, length, pos /* ignored */) {
    buffer = prepareBuffer(buffer, offset, length);
    return readWriteHelper(stream, () => stream.devops.read(buffer), "read");
  },
  write: function (stream, buffer, offset, length, pos /* ignored */): number {
    buffer = prepareBuffer(buffer, offset, length);
    return readWriteHelper(stream, () => stream.devops.write(buffer), "write");
  },
};

function refreshStreams() {
  if (!INITIALIZED) {
    return;
  }
  FS.closeStream(0 /* stdin */);
  FS.closeStream(1 /* stdout */);
  FS.closeStream(2 /* stderr */);
  FS.open("/dev/stdin", cDefs.O_RDONLY);
  FS.open("/dev/stdout", cDefs.O_WRONLY);
  FS.open("/dev/stderr", cDefs.O_WRONLY);
}

/**
 * This is called at the end of loadPyodide to set up the streams. If
 * loadPyodide has been given stdin, stdout, stderr arguments they are provided
 * here. Otherwise, we set the default behaviors. This also fills in the global
 * state in this file.
 * @param stdin
 * @param stdout
 * @param stderr
 * @private
 */
API.initializeStreams = function (
  stdin?: InFuncType,
  stdout?: (a: string) => void,
  stderr?: (a: string) => void,
) {
  const major = FS.createDevice.major++;
  DEVS.stdin = FS.makedev(major, 0);
  DEVS.stdout = FS.makedev(major, 1);
  DEVS.stderr = FS.makedev(major, 2);

  FS.registerDevice(DEVS.stdin, stream_ops);
  FS.registerDevice(DEVS.stdout, stream_ops);
  FS.registerDevice(DEVS.stderr, stream_ops);

  FS.unlink("/dev/stdin");
  FS.unlink("/dev/stdout");
  FS.unlink("/dev/stderr");

  FS.mkdev("/dev/stdin", DEVS.stdin);
  FS.mkdev("/dev/stdout", DEVS.stdout);
  FS.mkdev("/dev/stderr", DEVS.stderr);

  setStdin({ stdin });
  setStdout({ batched: stdout });
  setStderr({ batched: stderr });

  INITIALIZED = true;
  refreshStreams();
};

/**
 * Sets the default stdin. If in node, stdin will read from `process.stdin`
 * and isatty(stdin) will be set to tty.isatty(process.stdin.fd).
 * If in a browser, this calls setStdinError.
 */
function setDefaultStdin() {
  if (RUNTIME_ENV.IN_NODE) {
    setStdin(new NodeReader(process.stdin));
  } else {
    setStdin({ stdin: () => prompt() });
  }
}

/**
 * Sets isatty(stdin) to false and makes reading from stdin always set an EIO
 * error.
 */
function setStdinError() {
  _setStdinOps(new ErrorReader());
  refreshStreams();
}

type StdinOptions = {
  stdin?: InFuncType;
  error?: boolean;
  isatty?: boolean;
  autoEOF?: boolean;
};

/**
 * Set a stdin handler. See :ref:`redirecting standard streams <streams-stdin>`
 * for a more detailed explanation. There are two different possible interfaces
 * to implement a handler. It's also possible to select either the default
 * handler or an error handler that always returns an IO error.
 *
 * 1. passing a ``read`` function (see below),
 * 2. passing a ``stdin`` function (see below),
 * 3. passing ``error: true`` indicates that attempting to read from stdin
 *    should always raise an IO error.
 * 4. passing none of these sets the default behavior. In node, the default is
 *    to read from stdin. In the browser, the default is to raise an error.
 *
 * The functions on the ``options`` argument will be called with ``options``
 * bound to ``this`` so passing an instance of a class as the ``options`` object
 * works as expected.
 *
 * The interfaces that the handlers implement are as follows:
 *
 * 1. The ``read`` function is called with a ``Uint8Array`` argument. The
 *    function should place the utf8-encoded input into this buffer and return
 *    the number of bytes written. For instance, if the buffer was completely
 *    filled with input, then return `buffer.length`. If a ``read`` function is
 *    passed you may optionally also pass an ``fsync`` function which is called
 *    when stdin is flushed.
 *
 * 2. The ``stdin`` function is called with zero arguments. It should return one
 *    of:
 *
 *    - :js:data:`null` or :js:data:`undefined`: these are interpreted as end of
 *      file.
 *    - a number
 *    - a string
 *    - an :js:class:`ArrayBuffer` or :js:class:`TypedArray` with
 *      :js:data:`~TypedArray.BYTES_PER_ELEMENT` equal to 1. The buffer should
 *      contain utf8 encoded text.
 *
 *    If a number is returned, it is interpreted as a single character code. The
 *    number should be between 0 and 255.
 *
 *    If a string is returned, it is encoded into a buffer using
 *    :js:class:`TextEncoder`. By default, an EOF is appended after each string
 *    or buffer returned. If this behavior is not desired, pass `autoEOF: false`.
 *
 * @param options.stdin A stdin handler
 * @param options.read A read handler
 * @param options.error If this is set to ``true``, attempts to read from stdin
 * will always set an IO error.
 * @param options.isatty Should :py:func:`isatty(stdin) <os.isatty>` be ``true``
 * or ``false`` (default ``false``).
 * @param options.autoEOF Insert an EOF automatically after each string or
 * buffer? (default ``true``). This option can only be used with the stdin
 * handler.
 */
export function setStdin(
  options: {
    stdin?: InFuncType;
    read?: (buffer: Uint8Array) => number;
    error?: boolean;
    isatty?: boolean;
    autoEOF?: boolean;
  } = {},
) {
  let { stdin, error, isatty, autoEOF, read } = options as StdinOptions &
    Partial<Reader>;
  const numset = +!!stdin + +!!error + +!!read;
  if (numset > 1) {
    throw new TypeError(
      "At most one of stdin, read, and error must be provided.",
    );
  }
  if (!stdin && autoEOF !== undefined) {
    throw new TypeError(
      "The 'autoEOF' option can only be used with the 'stdin' option",
    );
  }
  if (numset === 0) {
    setDefaultStdin();
    return;
  }
  if (error) {
    setStdinError();
  }
  if (stdin) {
    autoEOF = autoEOF === undefined ? true : autoEOF;
    _setStdinOps(new LegacyReader(stdin.bind(options), !!isatty, autoEOF));
  }
  if (read) {
    _setStdinOps(options as Reader);
  }
  refreshStreams();
}

/**
 * A batched handler to provide to :js:func:`~pyodide.setStdout` or
 * :js:func:`~pyodide.setStderr`.
 *
 * The ``handler.batched()`` handler is called with a string whenever a newline
 * character is written or stdout is flushed. In the former case, the received
 * line will end with a newline, in the latter case it will not. Streams
 * implemented with a batched handlers cannot be a tty.
 */
export interface BatchedWriteHandler {
  batched: (output: string) => void;
}

/**
 * A raw handler to provide to :js:func:`~pyodide.setStdout` or
 * :js:func:`~pyodide.setStderr`.
 *
 * The ``handler.raw()`` function is called once with each byte written to the
 * stream as an argument.
 *
 * ``isatty`` controls whether `isatty()` returns `true` or `false` for the
 * stream. It defaults to `false`.
 *
 * If present, and `isatty` is `true`, `getTerminalSize()` controls the size of
 * the terminal reported by the tiocgwinsz ioctl, which propagates to
 * `os.get_terminal_size()`. If absent, the terminal size is reported as 24 rows
 * by 80 columns.
 */
export interface RawWriteHandler {
  raw: (charCode: number) => void;
  isatty?: boolean;
  getTerminalSize?: () => { rows: number; columns: number } | undefined;
}

type StdWriteOpts = BatchedWriteHandler | RawWriteHandler | Writer;
type StdWriteOptsAll = Partial<BatchedWriteHandler & RawWriteHandler & Writer>;

function _setStdwrite(
  options: StdWriteOpts | {},
  setOps: (ops: Writer) => void,
  getDefaults: () => StdWriteOpts,
) {
  let opts = options as StdWriteOptsAll;
  let { raw, isatty, batched, write } = opts;
  if (!raw && !write && isatty) {
    throw new TypeError(
      "Cannot set 'isatty' to true unless 'raw' or 'write' is provided",
    );
  }
  let nset = +!!raw + +!!batched + +!!write;
  if (nset > 1) {
    throw new TypeError(
      "At most one of 'raw', 'batched', and 'write' must be passed",
    );
  }
  if (nset === 0) {
    opts = getDefaults();
    ({ raw, isatty, batched, write } = opts);
  }
  if (raw) {
    setOps(new CharacterCodeWriter(opts as RawWriteHandler));
  }
  if (batched) {
    setOps(new StringWriter(batched.bind(opts)));
  }
  if (write) {
    setOps(opts as Writer);
  }
  refreshStreams();
}

/**
 * If in node, sets stdout to write directly to process.stdout and sets isatty(stdout)
 * to tty.isatty(process.stdout.fd).
 * If in a browser, sets stdout to write to console.log and sets isatty(stdout) to false.
 */
function _getStdoutDefaults(): StdWriteOpts {
  if (RUNTIME_ENV.IN_NODE) {
    return new NodeWriter(process.stdout);
  } else {
    return { batched: (x) => console.log(x) };
  }
}

/**
 * If in node, sets stdout to write directly to process.stdout and sets isatty(stdout)
 * to tty.isatty(process.stdout.fd).
 * If in a browser, sets stdout to write to console.log and sets isatty(stdout) to false.
 */
function _getStderrDefaults(): StdWriteOpts {
  if (RUNTIME_ENV.IN_NODE) {
    return new NodeWriter(process.stderr);
  } else {
    return { batched: (x) => console.warn(x) };
  }
}

/**
 * Sets the standard out handler. A :js:class:`BatchedWriteHandler`, a
 * :js:class:`RawWriteHandler`, or a :js:class:`Writer` can be provided. See the
 * documentation for these types for more information about how each works. If
 * no handler is provided, we restore the default handler. Passing a `Writer`
 * provides the most flexibility and the best performance.
 *
 * @example
 * async function main(){
 *   const pyodide = await loadPyodide();
 *   pyodide.setStdout({ batched: (msg) => console.log(msg) });
 *   pyodide.runPython("print('ABC')");
 *   // 'ABC'
 *   pyodide.setStdout({ raw: (byte) => console.log(byte) });
 *   pyodide.runPython("print('ABC')");
 *   // 65
 *   // 66
 *   // 67
 *   // 10 (the ascii values for 'ABC' including a new line character)
 * }
 * main();
 */
export function setStdout(options?: StdWriteOpts | {}) {
  _setStdwrite(options ?? {}, _setStdoutOps, _getStdoutDefaults);
}

/**
 * Sets the standard error handler. A :js:typealias:`BatchedWriteHandler`, a
 * :js:typealias:`RawWriteHandler`, or a :js:typealias:`Writer` can be provided.
 * See the documentation for these types for more information about how each
 * works. If no handler is provided, we restore the default handler. Passing a
 * `Writer` provides the most flexibility and the best performance.
 */
export function setStderr(options?: StdWriteOpts | {}) {
  _setStdwrite(options ?? {}, _setStderrOps, _getStderrDefaults);
}

const _TextEncoder = globalThis.TextEncoder ?? function () {};
const textencoder = new _TextEncoder();

// Reader implementations

class ErrorReader {
  read(buffer: Uint8Array): number {
    // always set an IO error.
    throw new FS.ErrnoError(cDefs.EIO);
  }
}

type NodeReadStream = NodeJS.ReadStream & { fd: number };

class NodeReader implements Reader {
  stream: NodeReadStream;
  isatty: boolean;

  constructor(stream: NodeReadStream) {
    this.stream = stream;
    this.isatty = tty.isatty(stream.fd);
  }

  read(buffer: Uint8Array): number {
    try {
      return fs.readSync(this.stream.fd, buffer);
    } catch (e) {
      // Platform differences: on Windows, reading EOF throws an exception,
      // but on other OSes, reading EOF returns 0. Uniformize behavior by
      // catching the EOF exception and returning 0.
      if ((e as Error).toString().includes("EOF")) {
        return 0;
      }
      throw e;
    }
  }

  fsync() {
    nodeFsync(this.stream.fd);
  }
}

class LegacyReader {
  infunc: InFuncType;
  autoEOF: boolean;
  index: number;
  saved: Uint8Array | string | undefined;
  insertEOF: boolean;
  isatty: boolean;

  constructor(infunc: InFuncType, isatty: boolean, autoEOF: boolean) {
    this.infunc = infunc;
    this.isatty = isatty;
    this.autoEOF = autoEOF;
    this.index = 0;
    this.saved = undefined;
    this.insertEOF = false;
  }

  _getInput(): Uint8Array | string | number | undefined {
    if (this.saved) {
      return this.saved;
    }
    let val = this.infunc();
    if (typeof val === "number") {
      return val;
    }
    if (val === undefined || val === null) {
      return undefined;
    }
    if (ArrayBuffer.isView(val)) {
      if ((val as any).BYTES_PER_ELEMENT !== 1) {
        console.warn(
          `Expected BYTES_PER_ELEMENT to be 1, infunc gave ${val.constructor}`,
        );
        throw new FS.ErrnoError(cDefs.EIO);
      }
      return val;
    }
    if (typeof val === "string") {
      if (!val.endsWith("\n")) {
        val += "\n";
      }
      return val;
    }
    if (Object.prototype.toString.call(val) === "[object ArrayBuffer]") {
      return new Uint8Array(val as ArrayBuffer);
    }
    console.warn(
      "Expected result to be undefined, null, string, array buffer, or array buffer view",
    );
    throw new FS.ErrnoError(cDefs.EIO);
  }

  read(buffer: Uint8Array): number {
    if (this.insertEOF) {
      this.insertEOF = false;
      return 0;
    }
    let bytesRead = 0;
    while (true) {
      let val = this._getInput();
      if (typeof val === "number") {
        buffer[0] = val;
        buffer = buffer.subarray(1);
        bytesRead++;
        continue;
      }
      let lastwritten;
      if (val && val.length > 0) {
        if (typeof val === "string") {
          let { read, written } = textencoder.encodeInto(val, buffer);
          this.saved = val.slice(read);
          bytesRead += written!;
          lastwritten = buffer[written! - 1];
          buffer = buffer.subarray(written);
        } else {
          let written;
          if (val.length > buffer.length) {
            buffer.set(val.subarray(0, buffer.length));
            this.saved = val.subarray(buffer.length);
            written = buffer.length;
          } else {
            buffer.set(val);
            this.saved = undefined;
            written = val.length;
          }
          bytesRead += written;
          lastwritten = buffer[written - 1];
          buffer = buffer.subarray(written);
        }
      }
      if (!(val && val.length > 0) || this.autoEOF || buffer.length === 0) {
        this.insertEOF = bytesRead > 0 && this.autoEOF && lastwritten !== 10;
        return bytesRead;
      }
    }
  }

  fsync() {}
}

// Writer implementations

class CharacterCodeWriter implements Writer {
  options: RawWriteHandler;
  isatty: boolean;

  constructor(options: RawWriteHandler) {
    this.options = options;
    this.isatty = !!options.isatty;
  }

  write(buffer: Uint8Array) {
    for (let i of buffer) {
      this.options.raw(i);
    }
    return buffer.length;
  }

  getTerminalSize() {
    return this.options.getTerminalSize?.();
  }
}

class StringWriter implements Writer {
  out: (a: string) => void;
  isatty: boolean = false;
  output: number[];

  constructor(out: (a: string) => void) {
    this.out = out;
    this.output = [];
  }

  write(buffer: Uint8Array) {
    for (let val of buffer) {
      if (val === 10 /* charCode('\n') */) {
        this.out(UTF8ArrayToString(new Uint8Array(this.output)));
        this.output = [];
      } else if (val !== 0) {
        // val == 0 would cut text output off in the middle.
        this.output.push(val);
      }
    }
    return buffer.length;
  }

  fsync() {
    if (this.output && this.output.length > 0) {
      this.out(UTF8ArrayToString(new Uint8Array(this.output)));
      this.output = [];
    }
  }
}

type NodeWriteStream = NodeJS.WriteStream & { fd: number };

class NodeWriter implements Writer {
  stream: NodeWriteStream;
  isatty: boolean;
  constructor(stream: NodeWriteStream) {
    this.stream = stream;
    this.isatty = tty.isatty(stream.fd);
  }

  write(buffer: Uint8Array): number {
    return fs.writeSync(this.stream.fd, buffer);
  }

  fsync() {
    nodeFsync(this.stream.fd);
  }

  getTerminalSize() {
    return this.stream;
  }
}
