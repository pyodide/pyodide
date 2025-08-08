import "https://unpkg.com/@xterm/xterm@5.4.0/lib/xterm.js";
import "https://unpkg.com/@xterm/addon-fit@0.9.0/lib/addon-fit.js";

async function run() {
  const fitAddon = new FitAddon.FitAddon();
  const term = new Terminal({
    scrollback: 2_000,
    convertEol: true,
    fontSize: 16,
    lineHeight: 1.4,
    // fontFamily: "Monaco, Menlo, 'Courier New', monospace",
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

  // 2. Initialize Pyodide
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

  // 3. REPL implementation
  const ps1 = ">>> ";
  const ps2 = "... ";
  let buffer = "";
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
  }

  async function execLine(line) {
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
        term.write(prompt);
        break;
      case "\u0003": // Ctrl-C
        pyconsole.buffer.clear();
        buffer = "";
        term.write("^C\r\nKeyboardInterrupt\r\n" + ps1);
        prompt = ps1;
        historyIndex = null;
        break;
      case "\u007F": // Backspace
        if (buffer.length > 0) {
          buffer = buffer.slice(0, -1);
          term.write("\b \b");
        }
        break;
      case "\x1B[A": // Up arrow
        if (prompt === ps1) {
          if (historyIndex === null) historyIndex = history.length;
          if (historyIndex > 0) {
            historyIndex -= 1;
            buffer = history[historyIndex] || "";
            refreshLine();
          }
        }
        break;
      case "\x1B[B": // Down arrow
        if (prompt === ps1 && historyIndex !== null) {
          if (historyIndex < history.length - 1) {
            historyIndex += 1;
            buffer = history[historyIndex] || "";
          } else {
            historyIndex = null;
            buffer = "";
          }
          refreshLine();
        }
        break;
      case "\x1B[C": // Right arrow - ignore
      case "\x1B[D": // Left arrow - ignore
        break;
      default:
        buffer += data;
        term.write(data);
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
