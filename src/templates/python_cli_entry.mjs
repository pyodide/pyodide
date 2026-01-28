import { loadPyodide } from "./pyodide.mjs";
import { readdirSync, statSync } from "fs";

/**
 * Determine which native top level directories to mount into the Emscripten
 * file system.
 *
 * This is a bit brittle, if the machine has a top level directory with certain
 * names it is possible this could break. The most surprising one here is tmp, I
 * am not sure why but if we link tmp then the process silently fails.
 */
function dirsToMount() {
  const filteredDirs = new Set([
    // Unix
    "dev",
    "lib",
    "proc",
  ]);

  return readdirSync("/")
    .filter((dir) => !filteredDirs.has(dir))
    .filter((dir) => !dir.startsWith("$")) // System directories in Windows, such as $Recycle.Bin
    .filter((dir) => {
      // Use stat to confirm this entry is a directory.
      try {
        const st = statSync("/" + dir);
        return st.isDirectory();
      } catch (e) {
        return false;
      }
    })
    .map((dir) => "/" + dir);
}

/**
 * Convert a Windows absolute path to a Unix-style path.
 * Strips the drive letter (e.g., "C:") and converts backslashes to forward slashes.
 *
 * @example
 * windowsPathToUnix("C:\\Users\\siha\\file.txt") // returns "/Users/siha/file.txt"
 * windowsPathToUnix("D:\\projects\\myapp") // returns "/projects/myapp"
 */
function windowsPathToUnix(path) {
  if (process.platform === "win32") {
    // Remove drive letter (e.g., "C:" or "D:")
    let unixPath = path.replace(/^[A-Za-z]:/, "");

    // Replace all backslashes with forward slashes
    unixPath = unixPath.replace(/\\/g, "/");

    return unixPath;
  }
  return path;
}

/**
 * Escape backslashes in a Windows path for use in Python strings.
 */
function escapeWindowsPath(path) {
  if (process.platform === "win32") {
    return path.replace(/\\/g, "\\\\");
  }
  return path;
}

const thisProgramFlag = "--this-program=";
const thisProgramIndex = process.argv.findIndex((x) =>
  x.startsWith(thisProgramFlag),
);
const args = process.argv.slice(thisProgramIndex + 1).map(windowsPathToUnix);
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

function patchPlatformForUv(py) {
  // UV uses sysconfig configs to determine platform details when installing
  // packages through `uv pip`. When running on Windows, we need to patch
  // sysconfig to return the correct values for a Windows platform.
  if (process.platform !== "win32" || process.env.UV === undefined) {
    return;
  }

  const virtualEnvPrefix = process.env.VIRTUAL_ENV || "/";
  py.runPython(
    `
    import sys
    import sysconfig
    import os, ntpath, posixpath
    sys.prefix = "${escapeWindowsPath(virtualEnvPrefix)}"
    sys.executable = "${escapeWindowsPath(_sysExecutable)}"
    sysconfig._INSTALL_SCHEMES['venv'] = sysconfig._INSTALL_SCHEMES['nt_venv']
    def _abspath(path):
      """uv tries to call abspath on a windows path, make it work"""
      if ntpath.isabs(path):
        return path
      elif posixpath.isabs(path):  # we cannot use posixpath.abspath directly here because it ends up infinite recursion
        return path
      else:
        return posixpath.abspath(path)
    os.path.abspath = _abspath
    `,
  );
}

function calculateSysPath(py) {
  // On windows, packages are installed in a different location (Lib\\site-packages)
  // compared to other platforms (lib/pythonX.Y/site-packages).
  // In this case, Python will not be able to setup the sys.path correctly by itself,
  // so we need to manually add the site-packages path to sys.path.
  if (process.platform === "win32") {
    const virtualEnvPrefix = process.env.VIRTUAL_ENV;
    if (!virtualEnvPrefix) {
      return;
    }

    const sitePackagesPath = `${virtualEnvPrefix}\\Lib\\site-packages`;
    // check if the path exists
    const stat = statSync(sitePackagesPath);
    if (!stat.isDirectory()) {
      return;
    }

    py.runPython(
      `
      import sys
      site_packages_path = "${windowsPathToUnix(sitePackagesPath)}"
      if site_packages_path not in sys.path:
          sys.path.append(site_packages_path)
      `,
    );
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
          // In Windows, passing _sysExecutable doesn't seem to set sys.executable to python.bat
          // since the python.bat batch file is not a real executable that Python interpreter can inspect.
          // Therefore, we force set PYTHONEXECUTABLE here to ensure sys.executable is correct.
          PYTHONEXECUTABLE: windowsPathToUnix(_sysExecutable),
        },
        process.env,
        { HOME: windowsPathToUnix(process.cwd()) },
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

  patchPlatformForUv(py);
  calculateSysPath(py);

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
