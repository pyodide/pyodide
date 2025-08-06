import ErrorStackParser, {
	StackFrame,
} from "../js/vendor/stackframe/error-stack-parser";
import "types";

declare var Tests: any;

function ensureCaughtObjectIsError(e: any): Error {
	if (typeof e === "string") {
		// Sometimes emscripten throws a raw string...
		e = new Error(e);
	} else if (e && typeof e === "object" && e.name === "ExitStatus") {
		let status = e.status;
		e = new Exit(e.message);
		e.status = status;
	} else if (
		typeof e !== "object" ||
		e === null ||
		typeof e.stack !== "string" ||
		typeof e.message !== "string"
	) {
		// We caught something really weird. Be brave!
		const typeTag = API.getTypeTag(e);
		let msg = `A value of type ${typeof e} with tag ${typeTag} was thrown as an error!`;
		try {
			msg += `\nString interpolation of the thrown value gives """${e}""".`;
		} catch (e) {
			msg += `\nString interpolation of the thrown value fails.`;
		}
		try {
			msg += `\nThe thrown value's toString method returns """${e.toString()}""".`;
		} catch (e) {
			msg += `\nThe thrown value's toString method fails.`;
		}
		e = new Error(msg);
	}
	// Post conditions:
	// 1. typeof e is object
	// 2. hiwire_is_error(e) returns true
	return e;
}

class CppException extends Error {
	ty: string;
	constructor(
		ty: string,
		msg: string | undefined,
		e: any /* WebAssembly.Exception */,
	) {
		// @ts-ignore
		const ptr = Module.getCppExceptionThrownObjectFromWebAssemblyException(e);
		if (!msg) {
			msg = `The exception is an object of type ${ty} at address ${ptr} which does not inherit from std::exception`;
		}
		super(msg);
		this.ty = ty;
	}
}
Object.defineProperty(CppException.prototype, "name", {
	get() {
		return `${this.constructor.name} ${this.ty}`;
	},
});

const WasmException = (WebAssembly as any).Exception;
const isWasmException = (e: any) => e instanceof WasmException;

function convertCppException(e: any) {
	let [ty, msg]: [string, string] = Module.getExceptionMessage(e);
	return new CppException(ty, msg, e);
}
Tests.convertCppException = convertCppException;

let fatal_error_occurred = false;
/**
 * Signal a fatal error.
 *
 * Dumps the Python traceback, shows a JavaScript traceback, and prints a clear
 * message indicating a fatal error. It then dummies out the public API so that
 * further attempts to use Pyodide will clearly indicate that Pyodide has failed
 * and can no longer be used. pyodide._module is left accessible, and it is
 * possible to continue using Pyodide for debugging purposes if desired.
 *
 * @argument e {Error} The cause of the fatal error.
 * @private
 */
API.fatal_error = function (e: any): never {
	if (e && e.pyodide_fatal_error) {
		// @ts-ignore
		return;
	}

	if (fatal_error_occurred) {
		console.error("Recursive call to fatal_error. Inner error was:");
		console.error(e);
		// @ts-ignore
		return;
	}
	if (e instanceof NoGilError) {
		throw e;
	}
	if (typeof e === "number" || isWasmException(e)) {
		// Hopefully a C++ exception?
		e = convertCppException(e);
	} else {
		e = ensureCaughtObjectIsError(e);
	}
	// Mark e so we know not to handle it later in EM_JS wrappers
	e.pyodide_fatal_error = true;
	fatal_error_occurred = true;
	const isexit = e instanceof Exit;
	if (!isexit) {
		console.error(
			"Pyodide has suffered a fatal error. Please report this to the Pyodide maintainers.",
		);
		console.error("The cause of the fatal error was:");
		if (API.inTestHoist) {
			// Test hoist won't print the error object in a useful way so convert it to
			// string.
			console.error(e.toString());
			console.error(e.stack);
		} else {
			console.error(e);
		}
	}
	try {
		if (!isexit) {
			_dump_traceback();
		}
		let reason = isexit ? "exited" : "fatally failed";
		let msg = `Pyodide already ${reason} and can no longer be used.`;
		for (let key of Reflect.ownKeys(API.public_api)) {
			if (
				(typeof key === "string" && key.startsWith("_")) ||
				key === "version"
			) {
				continue;
			}
			Object.defineProperty(API.public_api, key, {
				enumerable: true,
				configurable: true,
				get: () => {
					throw new Error(msg);
				},
			});
		}
		if (API.on_fatal) {
			API.on_fatal(e);
		}
	} catch (err2) {
		console.error("Another error occurred while handling the fatal error:");
		console.error(err2);
	}
	throw e;
};

/**
 * Signal a fatal error if the exception is not an expected exception.
 *
 * @argument e {any} The cause of the fatal error.
 * @private
 */
API.maybe_fatal_error = function (e: any) {
	// Emscripten throws "unwind" to stop current code and return to the main event loop.
	// This is expected behavior and should not be treated as a fatal error.
	// However, after the "unwind" exception is caught, the call stack is not unwound
	// properly and there are dead frames remaining on the stack.
	// This might cause problems in the future, so we need to find a way to fix it.
	// See: 1) https://github.com/emscripten-core/emscripten/issues/16071
	//      2) https://github.com/kitao/pyxel/issues/418
	if (API._skip_unwind_fatal_error && e === "unwind") {
		return;
	}

	API.fatal_error(e);
};

let stderr_chars: number[] = [];
API.capture_stderr = function () {
	stderr_chars = [];
	FS.createDevice("/dev", "capture_stderr", null, (e: number) =>
		stderr_chars.push(e),
	);
	FS.closeStream(2 /* stderr */);
	// open takes the lowest available file descriptor. Since 0 and 1 are occupied by stdin and stdout it takes 2.
	FS.open("/dev/capture_stderr", 1 /* O_WRONLY */);
};

API.restore_stderr = function () {
	FS.closeStream(2 /* stderr */);
	FS.unlink("/dev/capture_stderr");
	// open takes the lowest available file descriptor. Since 0 and 1 are occupied by stdin and stdout it takes 2.
	FS.open("/dev/stderr", 1 /* O_WRONLY */);
	return UTF8ArrayToString(new Uint8Array(stderr_chars));
};

API.fatal_loading_error = function (...args: string[]) {
	let message = args.join(" ");
	if (_PyErr_Occurred()) {
		API.capture_stderr();
		// Prints traceback to stderr
		_PyErr_Print();
		const captured_stderr = API.restore_stderr();
		message += "\n" + captured_stderr;
	}
	throw new FatalPyodideError(message);
};

function isPyodideFrame(frame: StackFrame): boolean {
	if (!frame) {
		return false;
	}
	const fileName = frame.fileName || "";
	if (fileName.includes("wasm-function")) {
		return true;
	}
	if (!fileName.includes("pyodide.asm.js")) {
		return false;
	}
	let funcName = frame.functionName || "";
	if (funcName.startsWith("Object.")) {
		funcName = funcName.slice("Object.".length);
	}
	if (
		API.public_api &&
		funcName in API.public_api &&
		funcName !== "PythonError"
	) {
		frame.functionName = funcName;
		return false;
	}
	return true;
}

function isErrorStart(frame: StackFrame): boolean {
	return isPyodideFrame(frame) && frame.functionName === "new_error";
}

Module.handle_js_error = function (e: any) {
	if (e && e.pyodide_fatal_error) {
		throw e;
	}
	if (e instanceof _PropagatePythonError) {
		// Python error indicator is already set in this case. If this branch is
		// not taken, Python error indicator should be unset, and we have to set
		// it. In this case we don't want to tamper with the traceback.
		return;
	}
	let restored_error = false;
	if (e instanceof PythonError) {
		// Try to restore the original Python exception.
		restored_error = _restore_sys_last_exception(e.__error_address);
	}
	let stack: any;
	let weirdCatch;
	try {
		stack = ErrorStackParser.parse(e);
	} catch (_) {
		weirdCatch = true;
	}
	if (weirdCatch) {
		e = ensureCaughtObjectIsError(e);
	}
	if (!restored_error) {
		// Wrap the JavaScript error
		let err = _JsProxy_create(e);
		_set_error(err);
		_Py_DecRef(err);
	}
	if (weirdCatch) {
		// In this case we have no stack frames so we can quit
		return;
	}
	if (isErrorStart(stack[0]) || isErrorStart(stack[1])) {
		while (isPyodideFrame(stack[0])) {
			stack.shift();
		}
	}
	// Add the Javascript stack frames to the Python traceback
	for (const frame of stack) {
		if (isPyodideFrame(frame)) {
			break;
		}
		const funcnameAddr = stringToNewUTF8(frame.functionName || "???");
		const fileNameAddr = stringToNewUTF8(frame.fileName || "???.js");
		__PyTraceback_Add(funcnameAddr, fileNameAddr, frame.lineNumber);
		_free(funcnameAddr);
		_free(fileNameAddr);
	}
};

/**
 * A JavaScript error caused by a Python exception.
 *
 * In order to reduce the risk of large memory leaks, the :js:class:`PythonError`
 * contains no reference to the Python exception that caused it. You can find
 * the actual Python exception that caused this error as
 * :py:data:`sys.last_exc`.
 *
 * See :ref:`type translations of errors <type-translations-errors>` for more
 * information.
 *
 * .. admonition:: Avoid leaking stack Frames
 *    :class: warning
 *
 *    If you make a :js:class:`~pyodide.ffi.PyProxy` of
 *    :py:data:`sys.last_exc`, you should be especially careful to
 *    :js:meth:`~pyodide.ffi.PyProxy.destroy` it when you are done. You may leak a large
 *    amount of memory including the local variables of all the stack frames in
 *    the traceback if you don't. The easiest way is to only handle the
 *    exception in Python.
 *
 * @hideconstructor
 */
export class PythonError extends Error {
	/**
	 * The address of the error we are wrapping. We may later compare this
	 * against sys.last_exc.
	 * WARNING: we don't own a reference to this pointer, dereferencing it
	 * may be a use-after-free error!
	 * @private
	 */
	__error_address: number;
	/**
	 * The name of the Python error class, e.g, :py:exc:`RuntimeError` or
	 * :py:exc:`KeyError`.
	 */
	type: string;
	constructor(type: string, message: string, error_address: number) {
		const oldLimit = Error.stackTraceLimit;
		Error.stackTraceLimit = Infinity;
		super(message);
		Error.stackTraceLimit = oldLimit;
		this.type = type;
		this.__error_address = error_address;
	}
}
API.PythonError = PythonError;

/**
 * A special marker. If we call a CPython API from an EM_JS function and the
 * CPython API sets an error, we might want to return an error status back to
 * C keeping the current Python error flag. This signals to the EM_JS wrappers
 * that the Python error flag is set and to leave it alone and return the
 * appropriate error value (either NULL or -1).
 * @hidden
 */
export class _PropagatePythonError extends Error {
	constructor() {
		super(
			"If you are seeing this message, an internal Pyodide error has " +
				"occurred. Please report it to the Pyodide maintainers.",
		);
	}
}
function setName(errClass: any) {
	Object.defineProperty(errClass.prototype, "name", {
		value: errClass.name,
	});
}

class FatalPyodideError extends Error {}
class Exit extends Error {}
class NoGilError extends Error {}
[
	_PropagatePythonError,
	FatalPyodideError,
	Exit,
	PythonError,
	NoGilError,
].forEach(setName);
API.NoGilError = NoGilError;

// Stolen from:
// https://github.com/sindresorhus/serialize-error/blob/main/error-constructors.js
API.errorConstructors = new Map(
	[
		// Native ES errors https://262.ecma-international.org/12.0/#sec-well-known-intrinsic-objects
		EvalError,
		RangeError,
		ReferenceError,
		SyntaxError,
		TypeError,
		URIError,

		// Built-in errors
		globalThis.DOMException,

		// Node-specific errors
		// https://nodejs.org/api/errors.html
		// @ts-ignore
		globalThis.AssertionError,
		// @ts-ignore
		globalThis.SystemError,
	]
		.filter((x) => x)
		.map((x) => [x.constructor.name, x]),
);

API.deserializeError = function (name: string, message: string, stack: string) {
	const cons = API.errorConstructors.get(name) || Error;
	const err = new cons(message);
	if (!API.errorConstructors.has(name)) {
		err.name = name;
	}
	err.message = message;
	err.stack = stack;
	return err;
};
