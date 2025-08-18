(accessing_files_quickref)=

# Accessing Files Quick Reference

For development of modules to use in Pyodide, the best experience comes from
using Pyodide in Node and mounting the development directory into Pyodide using
the NodeFS. In the NodeFS, all changes to your native file system are
immediately reflected in Pyodide and vice versa.

If your code is browser-only, you can use the Chrome `NativeFS` for development.
This will not automatically sync up with your native file system, but it is
still quite convenient.

## In Node.js

It's recommended to use {js:func}`pyodide.mountNodeFS` to mount the host file
system so that it is accessible from inside of Pyodide. For example if you have
a Python package in a folder called `my_package`, you can do:

```pyodide
pyodide.mountNodeFS("my_package", "/path/to/my_package");
pyodide.runPython(`
import my_package
# ... use it
`);
```

## In the browser

To access local files in Chrome, you can use the File System Access API to
acquire a directory handle and then mount the directory into the Pyodide file
system with {js:func}`pyodide.mountNativeFS`. To acquire the directory handle,
you have to fill out a folder picker the first time. The handle can subsequently
be stored in the `IndexedDB`. You will still be prompted for read and write
access, but you don't have to deal with the folder picker again.

The following code is a good starting point:

```js
const { get, set } = await import(
  "https://unpkg.com/idb-keyval@5.0.2/dist/esm/index.js"
);

/**
 * Mount a folder from your native filesystem as the directory
 * `pyodideDirectory`. If `directoryKey` was used previously, then it will reuse
 * the same folder as last time. Otherwise, it will show a directory picker.
 */
async function mountDirectory(pyodideDirectory, directoryKey) {
  let directoryHandle = await get(directoryKey);
  const opts = {
    id: "mountdirid",
    mode: "readwrite",
  };
  if (!directoryHandle) {
    directoryHandle = await showDirectoryPicker(opts);
    await set(directoryKey, directoryHandle);
  }
  const permissionStatus = await directoryHandle.requestPermission(opts);
  if (permissionStatus !== "granted") {
    throw new Error("readwrite access to directory not granted");
  }
  const { syncfs } = await pyodide.mountNativeFS(
    pyodideDirectory,
    directoryHandle,
  );
  return syncfs;
}
```

See {ref}`nativefs-api` for more information.

## Downloading external archives

If you are using Pyodide in the browser, you should download external files and
save them to the virtual file system. The recommended way to do this is to zip
the files and unpack them into the file system with
{js:func}`pyodide.unpackArchive`:

```pyodide
let zipResponse = await fetch("myfiles.zip");
let zipBinary = await zipResponse.arrayBuffer();
pyodide.unpackArchive(zipBinary, "zip");
```

You can also download the files from Python using
{py:func}`~pyodide.http.pyfetch`, which is a convenient wrapper of JavaScript
{js:func}`fetch`:

```pyodide
await pyodide.runPythonAsync(`
  from pyodide.http import pyfetch
  response = await pyfetch("https://some_url/myfiles.zip")
  await response.unpack_archive()
`)
```

For synchronous HTTP requests, you can use {py:func}`~pyodide.http.pyxhr`,
which provides a requests-like API using XMLHttpRequest:

```pyodide
pyodide.runPython(`
  from pyodide.http import pyxhr
  response = pyxhr.get("https://some_url/data.json")
  data = response.json()
  print(data)
`)
```

Note that `pyxhr` only works in browser environments and uses synchronous
XMLHttpRequest, which may block the main thread.
