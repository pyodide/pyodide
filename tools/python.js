#!/bin/sh
":" /* << "EOF"
This file is a bash/node polyglot.
*/;
`
EOF
# bash
set -e

which node > /dev/null  || { \
    >&2 echo "No node executable found on the path" && exit 1; \
}

ARGS=$(node -e "$(cat <<EOF
const major_version = Number(process.version.split(".")[0].slice(1));
if(major_version < 14) {
    console.error("Need node version >= 14. Got node version", process.version);
    process.exit(1);
}
if(major_version === 14){
    process.stdout.write("--experimental-wasm-bigint");
}
EOF
)")

exec node "$ARGS" "$0" "$@"
`;

const { loadPyodide } = require("../dist/pyodide");
const fs = require("fs");

function make_tty_ops(stream) {
    let newline = false;
    return {
        // get_char has 3 particular return values:
        // a.) the next character represented as an integer
        // b.) undefined to signal that no data is currently available
        // c.) null to signal an EOF
        get_char(tty) {
            if (newline) {
                newline = false;
                return null;
            }
            if (!tty.input.length) {
                var result = null;
                var BUFSIZE = 256;
                var buf = Buffer.alloc(BUFSIZE);
                var bytesRead = fs.readSync(0, buf, 0, BUFSIZE, -1);
                if (bytesRead === 0) {
                    return null;
                }
                result = buf.slice(0, bytesRead);
                tty.input = Array.from(result);
            }
            let res = tty.input.shift();
            newline = true;
            return res;
        },
        put_char(tty, val) {
            stream.write(Buffer.from([val]));
        },
        flush(tty) {},
    };
}

function setupStreams(FS, TTY) {
    let mytty = FS.makedev(FS.createDevice.major++, 0);
    let myttyerr = FS.makedev(FS.createDevice.major++, 0);
    TTY.register(mytty, make_tty_ops(process.stdout));
    TTY.register(myttyerr, make_tty_ops(process.stderr));
    FS.mkdev("/dev/mytty", mytty);
    FS.mkdev("/dev/myttyerr", myttyerr);
    FS.unlink("/dev/stdin");
    FS.unlink("/dev/stdout");
    FS.unlink("/dev/stderr");
    FS.symlink("/dev/mytty", "/dev/stdin");
    FS.symlink("/dev/mytty", "/dev/stdout");
    FS.symlink("/dev/myttyerr", "/dev/stderr");
    FS.closeStream(0);
    FS.closeStream(1);
    FS.closeStream(2);
    FS.open("/dev/stdin", 0);
    FS.open("/dev/stdout", 1);
    FS.open("/dev/stderr", 1);
}

const path = require("path");
function isSubdirectory(parent, dir) {
    const relative = path.relative(parent, dir);
    return relative && !relative.startsWith("..") && !path.isAbsolute(relative);
}

async function main() {
    let args = process.argv.slice(2);
    fs.writeFileSync("args.txt", args.toString());
    const homedir = require("os").homedir();
    let cwd = process.cwd();
    const _node_mounts = { [homedir]: homedir, "/usr/local": "/usr/local" };
    if (!isSubdirectory(homedir, cwd)) {
        _node_mounts[cwd] = cwd;
    }
    try {
        py = await loadPyodide({
            args,
            fullStdLib: false,
            _node_mounts,
            _working_directory: process.cwd(),
            stdout(e) {
                if (
                    [
                        "warning: no blob constructor, cannot create blobs with mimetypes",
                        "warning: no BlobBuilder",
                        "Python initialization complete",
                    ].includes(e)
                ) {
                    return;
                }
                console.log(e);
            },
        });
    } catch (e) {
        if (e.constructor.name !== "ExitStatus") {
            throw e;
        }
        process.exit(e.status);
    }
    const FS = py.FS;
    setupStreams(FS, py._module.TTY);
    let sideGlobals = py.runPython("{}");
    let resolveExit;
    let finishedPromise = new Promise((resolve) => {
        resolveExit = resolve;
    });
    globalThis.handleExit = function handleExit(code) {
        if (code === undefined) {
            code = 0;
        }
        resolveExit(code);
    };

    py.runPython(
        `
        import asyncio
        loop = asyncio.get_event_loop()
        loop._in_progress += 1
        from js import handleExit
        loop._no_in_progress_handler = handleExit
        loop._system_exit_handler = handleExit
        loop._keyboard_interrupt_handler = lambda: handleExit(130)
        import shutil
        from js.process import stdout
        import os
        def get_terminal_size(fallback=(80, 24)):
            columns = stdout.columns
            rows = stdout.rows
            if columns is None:
                columns = fallback[0]
            if rows is None:
                rows = fallback[1]
            return os.terminal_size((rows, columns))
        shutil.get_terminal_size = get_terminal_size
        `,
        { globals: sideGlobals }
    );

    let errcode = py._module._run_main();
    if (errcode) {
        process.exit(errcode);
    }
    py.runPython("loop._decrement_in_progress()", { globals: sideGlobals });
    process.exit(await finishedPromise);
}
main().catch((e) => {
    console.error(e);
    process.exit(1);
});
