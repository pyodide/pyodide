import { loadPyodide } from "./pyodide.mjs";
import { readdirSync } from "fs";

/**
 * Determine which native top level directories to mount into the Emscripten
 * file system.
 *
 * This is a bit brittle, if the machine has a top level directory with certain
 * names it is possible this could break. The most surprising one here is tmp, I
 * am not sure why but if we link tmp then the process silently fails.
 */
function dirsToMount() {
	return readdirSync("/")
		.filter((dir) => !["dev", "lib", "proc"].includes(dir))
		.map((dir) => "/" + dir);
}

const thisProgramFlag = "--this-program=";
const thisProgramIndex = process.argv.findIndex((x) =>
	x.startsWith(thisProgramFlag),
);
const args = process.argv.slice(thisProgramIndex + 1);
const _sysExecutable = process.argv[thisProgramIndex].slice(
	thisProgramFlag.length,
);

function fsInit(FS) {
	const mounts = dirsToMount();
	for (const mount of mounts) {
		FS.mkdirTree(mount);
		FS.mount(FS.filesystems.NODEFS, { root: mount }, mount);
	}
}

async function main() {
	let py;
	try {
		py = await loadPyodide({
			args,
			_sysExecutable,
			env: Object.assign(
				{
					PYTHONINSPECT: "",
				},
				process.env,
				{ HOME: process.cwd() },
			),
			fullStdLib: false,
			fsInit,
		});
	} catch (e) {
		if (e.constructor.name !== "ExitStatus") {
			throw e;
		}
		// If the user passed `--help`, `--version`, or a set of command line
		// arguments that is invalid in some way, we will exit here.
		process.exit(e.status);
	}
	py.setStdout();
	py.setStderr();
	let sideGlobals = py.runPython("{}");
	function handleExit(code) {
		if (code === undefined) {
			code = 0;
		}
		if (py._module._Py_FinalizeEx() < 0) {
			code = 120;
		}
		// It's important to call `process.exit` immediately after
		// `_Py_FinalizeEx` because otherwise any asynchronous tasks still
		// scheduled will segfault.
		process.exit(code);
	}
	sideGlobals.set("handleExit", handleExit);

	py.runPython(
		`
    from pyodide._package_loader import SITE_PACKAGES, should_load_dynlib
    from pyodide.ffi import to_js
    import re
    dynlibs_to_load = to_js([
        str(path) for path in SITE_PACKAGES.glob("**/*.so*")
        if should_load_dynlib(path)
    ])
    `,
		{ globals: sideGlobals },
	);
	const dynlibs = sideGlobals.get("dynlibs_to_load");
	for (const dynlib of dynlibs) {
		try {
			await py._module.API.loadDynlib(dynlib);
		} catch (e) {
			console.error("Failed to load lib ", dynlib);
			console.error(e);
		}
	}
	py.runPython(
		`
    import asyncio
    # Keep the event loop alive until all tasks are finished, or SystemExit or
    # KeyboardInterupt is raised.
    loop = asyncio.get_event_loop()
    # Make sure we don't run _no_in_progress_handler before we finish _run_main.
    loop._in_progress += 1
    loop._no_in_progress_handler = handleExit
    loop._system_exit_handler = handleExit
    loop._keyboard_interrupt_handler = lambda: handleExit(130)

    # Make shutil.get_terminal_size tell the terminal size accurately.
    import shutil
    from js.process import stdout
    import os
    def get_terminal_size(fallback=(80, 24)):
        columns = getattr(stdout, "columns", None)
        rows = getattr(stdout, "rows", None)
        if columns is None:
            columns = fallback[0]
        if rows is None:
            rows = fallback[1]
        return os.terminal_size((columns, rows))
    shutil.get_terminal_size = get_terminal_size
    `,
		{ globals: sideGlobals },
	);

	let errcode;
	try {
		if (py._module.jspiSupported) {
			errcode = await py._module.promisingRunMain();
		} else {
			errcode = py._module._run_main();
		}
	} catch (e) {
		if (e.constructor.name === "ExitStatus") {
			process.exit(e.status);
		}
		py._api.fatal_error(e);
	}
	if (errcode) {
		process.exit(errcode);
	}
	py.runPython("loop._decrement_in_progress()", { globals: sideGlobals });
}
main().catch((e) => {
	console.error(e);
	process.exit(1);
});
