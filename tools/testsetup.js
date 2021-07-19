Error.stackTraceLimit = Infinity;

// Fix globalThis is messed up in firefox see facebook/react#16606.
// Replace it with window.
globalThis.globalThis = globalThis.window || globalThis;

globalThis.sleep = function (s) {
    return new Promise((resolve) => setTimeout(resolve, s));
};

globalThis.assert = function (cb, message = "") {
    if (message !== "") {
        message = "\n" + message;
    }
    if (cb() !== true) {
        throw new Error(
            `Assertion failed: ${cb.toString().slice(6)}${message}`
        );
    }
};

globalThis.assertAsync = async function (cb, message = "") {
    if (message !== "") {
        message = "\n" + message;
    }
    if ((await cb()) !== true) {
        throw new Error(
            `Assertion failed: ${cb.toString().slice(12)}${message}`
        );
    }
};

function checkError(err, errname, pattern, pat_str, thiscallstr) {
    if (typeof pattern === "string") {
        pattern = new RegExp(pattern);
    }
    if (!err) {
        throw new Error(`${thiscallstr} failed, no error thrown`);
    }
    if (err.constructor.name !== errname) {
        throw new Error(
            `${thiscallstr} failed, expected error ` +
                `of type '${errname}' got type '${err.constructor.name}'`
        );
    }
    if (!pattern.test(err.message)) {
        throw new Error(
            `${thiscallstr} failed, expected error ` +
                `message to match pattern ${pat_str} got:\n${err.message}`
        );
    }
}

globalThis.assertThrows = function (cb, errname, pattern) {
    let pat_str = typeof pattern === "string" ? `"${pattern}"` : `${pattern}`;
    let thiscallstr = `assertThrows(${cb.toString()}, "${errname}", ${pat_str})`;
    let err = undefined;
    try {
        cb();
    } catch (e) {
        err = e;
    }
    checkError(err, errname, pattern, pat_str, thiscallstr);
};

globalThis.assertThrowsAsync = async function (cb, errname, pattern) {
    let pat_str = typeof pattern === "string" ? `"${pattern}"` : `${pattern}`;
    let thiscallstr = `assertThrowsAsync(${cb.toString()}, "${errname}", ${pat_str})`;
    let err = undefined;
    try {
        await cb();
    } catch (e) {
        err = e;
    }
    checkError(err, errname, pattern, pat_str, thiscallstr);
};
