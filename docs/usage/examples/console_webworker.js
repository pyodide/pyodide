// run pyodide interactively in a web-worker
import { loadPyodide } from "{{ PYODIDE_BASE_URL }}pyodide.mjs";

// functions to send messages back to client
function on_echo(msg, ...opts) {
	postMessage({ type: "echo", msg, opts });
}

function on_result(syntax_check, formatted_error) {
	postMessage({ type: "result", syntax_check, formatted_error });
}
function on_complete(result) {
	postMessage({ type: "complete", result });
}

function on_init(banner) {
	postMessage({ type: "init", banner });
}
function on_error(str) {
	postMessage({ type: "error", str });
}
function on_fatal(str) {
	postMessage({ type: "fatal", str });
}

var pyodide = await loadPyodide();

let { repr_shorten, BANNER, PyodideConsole } =
	pyodide.pyimport("pyodide.console");

// let client know we're alive and show our version banner
BANNER =
	"Running pyodide in webworker (i.e. The js object has no access to window)" +
	BANNER;
on_init(BANNER);

const pyconsole = PyodideConsole(pyodide.globals);

const namespace = pyodide.globals.get("dict")();
const await_fut = pyodide.runPython(
	`
import builtins
from pyodide.ffi import to_js

async def await_fut(fut):
    res = await fut
    if res is not None:
        builtins._ = res
    return to_js([res], depth=1)

await_fut
`,
	{ globals: namespace },
);
namespace.destroy();

pyconsole.stdout_callback = (s) => on_echo(s, { newline: false });

pyconsole.stderr_callback = (s) => {
	on_error(s.trimEnd());
};

pyodide._api.on_fatal = async (e) => {
	if (e.name === "Exit") {
		term.error(e);
		term.error("Pyodide exited and can no longer be used.");
	} else {
		term.error(
			"Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.",
		);
		term.error("The cause of the fatal error was:");
		term.error(e);
		term.error("Look in the browser console for more details.");
	}
	await term.ready;
	term.pause();
	await sleep(15);
	term.pause();
};

onmessage = async function (e) {
	const data = e.data;
	// push some text to the pyodide console
	if (data["type"] == "push") {
		const fut = pyconsole.push(data["value"]);
		const syntax_check = fut.syntax_check;
		const formatted_error = fut.formatted_error;
		if (fut.syntax_check == "complete") {
			const wrapped = await_fut(fut);
			try {
				const [value] = await wrapped;
				if (value !== undefined) {
					on_echo(
						repr_shorten.callKwargs(value, {
							separator: "\n<long output truncated>\n",
						}),
					);
				}
				if (value instanceof pyodide.ffi.PyProxy) {
					value.destroy();
				}
			} catch (e) {
				if (e.constructor.name === "PythonError") {
					const message = fut.formatted_error || e.message;
					on_error(message.trimEnd());
				} else {
					throw e;
				}
			} finally {
				fut.destroy();
				wrapped.destroy();
			}
		}
		on_result(syntax_check, formatted_error);
	} else if (data["type"] == "complete") {
		on_complete(pyconsole.complete(data["value"]).toJs()[0]);
	} else if (data["type"] == "clear") {
		pyconsole.buffer.clear();
	}
};
