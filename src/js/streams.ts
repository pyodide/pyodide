import { IN_NODE } from "./compat.js";
import type { Module } from "./module";

declare var API: any;
declare var Module: Module;

const FS = Module.FS;
const TTY = Module.TTY;

let INITIALIZED = false;

const ttyout_dev = FS.makedev(5, 0);
const ttyerr_dev = FS.makedev(6, 0);

type GetCharType = (tty: any) => null | number;
type InFuncType = () =>
  | null
  | undefined
  | string
  | ArrayBuffer
  | ArrayBufferView;

type PutCharType = {
  put_char: (tty: any, val: number) => void;
  fsync: (tty: any) => void;
};

type TtyOps = {
  get_char: GetCharType;
} & PutCharType;

const ttyout_ops: TtyOps = {
  get_char: () => {
    throw 0;
  },
  put_char: () => {
    throw 0;
  },
  fsync: () => {
    throw 0;
  },
};
const ttyerr_ops: TtyOps = {
  get_char: () => {
    throw 0;
  },
  put_char: () => {
    throw 0;
  },
  fsync: () => {
    throw 0;
  },
};
const isattys = {
  stdin: false,
  stdout: false,
  stderr: false,
};

const textencoder = new TextEncoder();
const textdecoder = new TextDecoder();

function make_get_char(infunc: InFuncType): GetCharType {
  let index = 0;
  let buf: Uint8Array = new Uint8Array(0);
  // get_char has 3 particular return values:
  // a.) the next character represented as an integer
  // b.) undefined to signal that no data is currently available
  // c.) null to signal an EOF
  return function get_char(tty: any) {
    try {
      if (index >= buf.length) {
        let input = infunc();
        if (input === undefined || input === null) {
          return null;
        }
        if (typeof input === "string") {
          if (!input.endsWith("\n")) {
            input += "\n";
          }
          buf = textencoder.encode(input);
        } else if (ArrayBuffer.isView(input)) {
          if ((input as any).BYTES_PER_ELEMENT !== 1) {
            throw new Error("Expected BYTES_PER_ELEMENT to be 1");
          }
          buf = input as Uint8Array;
        } else if (
          Object.prototype.toString.call(input) === "[object ArrayBuffer]"
        ) {
          buf = new Uint8Array(input);
        } else {
          throw new Error(
            "Expected result to be undefined, null, string, array buffer, or array buffer view",
          );
        }
        if (buf.length === 0) {
          return null;
        }
        index = 0;
      }
      return buf[index++];
    } catch (e) {
      // emscripten will catch this and set an IOError which is unhelpful for
      // debugging.
      console.error("Error thrown in stdin:");
      console.error(e);
      throw e;
    }
  };
}

function make_unbatched_put_char(out: (a: number) => void): PutCharType {
  return {
    put_char(tty: any, val: any) {
      out(val);
    },
    fsync() {},
  };
}

function make_batched_put_char(out: (a: string) => void): PutCharType {
  let output: number[] = [];
  return {
    // get_char has 3 particular return values:
    // a.) the next character represented as an integer
    // b.) undefined to signal that no data is currently available
    // c.) null to signal an EOF,
    put_char(tty: any, val: number) {
      if (val === null || val === 10 /* charCode('\n') */) {
        out(textdecoder.decode(new Uint8Array(output)));
        output = [];
      } else {
        if (val !== 0) {
          output.push(val); // val == 0 would cut text output off in the middle.
        }
      }
    },
    fsync(tty: any) {
      if (output && output.length > 0) {
        out(textdecoder.decode(new Uint8Array(output)));
        output = [];
      }
    },
  };
}

/**
 *
 * @param stdin
 * @param stdout
 * @param stderr
 * @private
 */
API.setStandardStreams = function (
  stdin?: InFuncType,
  stdout?: (a: string) => void,
  stderr?: (a: string) => void,
) {
  if (!stdin && IN_NODE) {
    const BUFSIZE = 256;
    const buf = Buffer.alloc(BUFSIZE);
    stdin = function () {
      const fs = require("fs");
      const bytesRead = fs.readSync(0, buf, 0, BUFSIZE, -1);
      if (bytesRead === 0) {
        return null;
      }
    };
  }
  setStdin(stdin);
  if (stdout) {
    setStdout(stdout);
  } else {
    setDefaultStdout();
  }

  if (stderr) {
    setStderr(stderr);
  } else {
    setDefaultStderr();
  }

  TTY.register(ttyout_dev, ttyout_ops);
  TTY.register(ttyerr_dev, ttyerr_ops);
  INITIALIZED = true;
  refreshStreams();
};

export function setStdin(
  stdin: InFuncType | undefined,
  isatty: boolean = false,
) {
  isattys.stdin = isatty;
  let get_char;
  if (stdin) {
    get_char = make_get_char(stdin);
  } else {
    get_char = () => {
      console.warn("get_char EIO");
      throw 0;
    };
  }
  ttyout_ops.get_char = get_char;
  ttyerr_ops.get_char = get_char;
}

export function setDefaultStdout() {
  if (IN_NODE) {
    setRawStdout((x) => process.stdout.write(Buffer.from([x])));
  } else {
    setStdout((x) => console.log(x));
  }
}

export function setStdout(
  stdout: (a: string) => void,
  isatty: boolean = false,
) {
  isattys.stdout = isatty;
  Object.assign(ttyout_ops, make_batched_put_char(stdout));
  refreshStreams();
}

export function setRawStdout(
  rawstdout: (a: number) => void,
  isatty: boolean = true,
) {
  isattys.stdout = isatty;
  Object.assign(ttyout_ops, make_unbatched_put_char(rawstdout));
  refreshStreams();
}

export function setDefaultStderr() {
  if (IN_NODE) {
    setRawStderr((x) => process.stderr.write(Buffer.from([x])));
  } else {
    setStderr((x) => console.log(x));
  }
}

export function setStderr(
  stderr: (a: string) => void,
  isatty: boolean = false,
) {
  isattys.stderr = isatty;
  Object.assign(ttyerr_ops, make_batched_put_char(stderr));
  refreshStreams();
}

export function setRawStderr(
  rawstderr: (a: number) => void,
  isatty: boolean = true,
) {
  isattys.stderr = isatty;
  Object.assign(ttyerr_ops, make_unbatched_put_char(rawstderr));
  refreshStreams();
}

function refreshStreams() {
  if (!INITIALIZED) {
    return;
  }
  FS.unlink("/dev/stdin");
  FS.unlink("/dev/stdout");
  FS.unlink("/dev/stderr");
  if (isattys.stdin) {
    FS.symlink("/dev/tty", "/dev/stdin");
  } else {
    FS.createDevice("/dev", "stdin", ttyout_ops.get_char.bind(0, 0));
  }
  if (isattys.stdout) {
    FS.symlink("/dev/tty", "/dev/stdout");
  } else {
    FS.createDevice("/dev", "stdout", null, ttyout_ops.put_char.bind(0, 0));
  }
  if (isattys.stderr) {
    FS.symlink("/dev/tty", "/dev/stderr");
  } else {
    FS.createDevice("/dev", "stderr", null, ttyerr_ops.put_char.bind(0, 0));
  }

  // Refresh std streams so they use our new versions
  FS.closeStream(0 /* stdin */);
  FS.closeStream(1 /* stdout */);
  FS.closeStream(2 /* stderr */);
  FS.open("/dev/stdin", 0 /* write only */);
  FS.open("/dev/stdout", 1 /* read only */);
  FS.open("/dev/stderr", 1 /* read only */);
}
