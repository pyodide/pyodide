import "https://unpkg.com/@xterm/xterm@5.4.0/lib/xterm.js";
import "https://unpkg.com/@xterm/addon-fit@0.9.0/lib/addon-fit.js";

async function run() {
  const fitAddon = new FitAddon.FitAddon();
  const term = new Terminal({
    cursorBlink: true,
    cursorStyle: "block",
    convertEol: true,
    scrollback: 2_000,
    fontSize: 18,
    lineHeight: 1.4,
    fontFamily: "monospace",
    theme: {
      background: "#000000",
      foreground: "#ffffff",
      cursor: "#ffffff",
      selection: "#404040",
      error: "#ff0000",
    },
  });

  term.open(document.getElementById("terminal"));
  term.loadAddon(fitAddon);

  fitAddon.fit();
  term.focus();

  window.addEventListener("resize", () => {
    setTimeout(() => fitAddon.fit(), 50);
  });

  // Re-fit after the page has fully loaded
  window.addEventListener("load", () => {
    setTimeout(() => fitAddon.fit(), 100);
  });

  // Initialize Pyodide
  let indexURL = "{{ PYODIDE_BASE_URL }}";
  const urlParams = new URLSearchParams(window.location.search);
  const buildParam = urlParams.get("build");
  if (buildParam && ["full", "debug", "pyc"].includes(buildParam)) {
    indexURL = indexURL.replace("/full/", "/" + buildParam + "/");
  }

  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  const pyodide = await loadPyodide();
  globalThis.pyodide = pyodide;

  const { repr_shorten, BANNER, PyodideConsole } =
    pyodide.pyimport("pyodide.console");

  term.writeln(
    `Welcome to the Pyodide ${pyodide.version} terminal emulator 🐍\n${BANNER}`,
  );

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

  pyconsole.stdout_callback = (s) => term.write(s);
  pyconsole.stderr_callback = (s) => term.write(`\x1b[31m${s}\x1b[0m`);

  // REPL implementation
  const ps1 = ">>> ";
  const ps2 = "... ";
  let buffer = "";
  let cursorIndex = 0; // index within buffer for in-line editing
  let prompt = ps1;
  const history = [];
  let historyIndex = null; // null means not navigating history

  term.write(prompt);

  function addToHistory(command) {
    const trimmed = command.trimEnd();
    if (!trimmed) return;
    const last = history[history.length - 1];
    if (last !== trimmed) history.push(trimmed);
  }

  function refreshLine() {
    // Move to start of line, rewrite prompt, clear to end, then write buffer
    term.write("\r");
    term.write(prompt);
    term.write("\x1b[0K");
    term.write(buffer);
    // Position the terminal cursor to reflect cursorIndex
    const distanceFromEnd = buffer.length - cursorIndex;
    if (distanceFromEnd > 0) {
      term.write(`\x1b[${distanceFromEnd}D`);
    }
  }

  function setBuffer(newBuffer, newCursorIndex = null) {
    buffer = newBuffer;
    if (newCursorIndex === null) {
      cursorIndex = buffer.length;
    } else {
      cursorIndex = Math.max(0, Math.min(newCursorIndex, buffer.length));
    }
    refreshLine();
  }

  async function execLine(line) {
    // clear the terminal
    if (line === "clear") {
      term.write("\x1b[2J\x1b[H");
      return;
    }

    const fut = pyconsole.push(line);

    switch (fut.syntax_check) {
      case "syntax-error":
        term.write(`\x1b[31m${fut.formatted_error.trimEnd()}\x1b[0m`);
        term.write("\r\n");
        prompt = ps1;
        addToHistory(line);
        historyIndex = null;
        fut.destroy();
        break;
      case "incomplete":
        prompt = ps2;
        addToHistory(line);
        historyIndex = null;
        return;
      case "complete":
        prompt = ps1;
        try {
          const wrapped = await_fut(fut);
          const [value] = await wrapped;
          if (value !== undefined) {
            const output = repr_shorten.callKwargs(value, {
              separator: "\n<long output truncated>\n",
            });
            term.write(output);
            term.write("\r\n");
          }
          if (value instanceof pyodide.ffi.PyProxy) value.destroy();
          wrapped.destroy();
        } catch (e) {
          const msg = fut.formatted_error || e.message;
          term.write(`\x1b[31m${String(msg).trimEnd()}\x1b[0m`);
          term.write("\r\n");
        } finally {
          fut.destroy();
        }
        addToHistory(line);
        historyIndex = null;
        break;
      default:
        term.write(`\r\nUnexpected syntax_check value: ${fut.syntax_check}`);
    }
  }

  term.onData(async (data) => {
    switch (data) {
      case "\r": // Enter
        term.write("\r\n");
        await execLine(buffer);
        buffer = "";
        cursorIndex = 0;
        term.write(prompt);
        break;
      case "\u0003": // Ctrl-C
        pyconsole.buffer.clear();
        buffer = "";
        cursorIndex = 0;
        term.write("^C\r\nKeyboardInterrupt\r\n" + ps1);
        prompt = ps1;
        historyIndex = null;
        break;
      case "\u007F": // Backspace
        if (cursorIndex > 0) {
          const before = buffer.slice(0, cursorIndex - 1);
          const after = buffer.slice(cursorIndex);
          cursorIndex -= 1;
          setBuffer(before + after, cursorIndex);
        }
        break;
      case "\x1B[A": // Up arrow
        if (prompt === ps1) {
          if (historyIndex === null) historyIndex = history.length;
          if (historyIndex > 0) {
            historyIndex -= 1;
            const newBuf = history[historyIndex] || "";
            setBuffer(newBuf, newBuf.length);
          }
        }
        break;
      case "\x1B[B": // Down arrow
        if (prompt === ps1 && historyIndex !== null) {
          if (historyIndex < history.length - 1) {
            historyIndex += 1;
            const newBuf = history[historyIndex] || "";
            setBuffer(newBuf, newBuf.length);
          } else {
            historyIndex = null;
            setBuffer("", 0);
          }
        }
        break;
      case "\x1B[C": // Right arrow
        if (cursorIndex < buffer.length) {
          cursorIndex += 1;
          refreshLine();
          break;
        }
      case "\x1B[D": // Left arrow
        if (cursorIndex > 0) {
          cursorIndex -= 1;
          refreshLine();
        }
        break;
      default:
        if (data) {
          // Insert arbitrary string at cursor position
          const before = buffer.slice(0, cursorIndex);
          const after = buffer.slice(cursorIndex);
          const newBuf = before + data + after;
          const newCursor = cursorIndex + data.length;
          setBuffer(newBuf, newCursor);
        }
    }
  });

  // 4. Extra features
  let idbkvPromise;
  async function getIDBKV() {
    if (!idbkvPromise) {
      idbkvPromise = await import(
        "https://unpkg.com/idb-keyval@5.0.2/dist/esm/index.js"
      );
    }
    return idbkvPromise;
  }

  async function mountDirectory(pyodideDirectory, directoryKey) {
    if (pyodide.FS.analyzePath(pyodideDirectory).exists) {
      return;
    }
    const { get, set } = await getIDBKV();
    const opts = { id: "mountdirid", mode: "readwrite" };
    let directoryHandle = await get(directoryKey);
    if (!directoryHandle) {
      directoryHandle = await showDirectoryPicker(opts);
      await set(directoryKey, directoryHandle);
    }
    const permissionStatus = await directoryHandle.requestPermission(opts);
    if (permissionStatus !== "granted") {
      throw new Error("readwrite access to directory not granted");
    }
    await pyodide.mountNativeFS(pyodideDirectory, directoryHandle);
  }
  globalThis.mountDirectory = mountDirectory;
}

run();
