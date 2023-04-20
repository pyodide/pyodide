(file-system)=

# Dealing with the file system

Pyodide includes a file system provided by Emscripten. In JavaScript, the
Pyodide file system can be accessed through {js:attr}`pyodide.FS` which re-exports
the [Emscripten File System
API](https://emscripten.org/docs/api_reference/Filesystem-API.html#filesystem-api)

**Example: Reading from the file system**

```js
pyodide.runPython(`
  with open("/hello.txt", "w") as fh:
      fh.write("hello world!")
`);

let file = pyodide.FS.readFile("/hello.txt", { encoding: "utf8" });
console.log(file); // ==> "hello world!"
```

**Example: Writing to the file system**

```js
let data = "hello world!";
pyodide.FS.writeFile("/hello.txt", data, { encoding: "utf8" });
pyodide.runPython(`
  with open("/hello.txt", "r") as fh:
        data = fh.read()
  print(data)
`);
```

## Mounting a file system

The default file system used in Pyodide is [MEMFS](https://emscripten.org/docs/api_reference/Filesystem-API.html#memfs),
which is a virtual in-memory file system. The data stored in MEMFS will be lost when the page is reloaded.

If you wish for files to persist, you can mount other file systems.
Other file systems provided by Emscripten are `IDBFS`, `NODEFS`, `PROXYFS`, `WORKERFS`.
Note that some filesystems can only be used in specific runtime environments.
See [Emscripten File System API](https://emscripten.org/docs/api_reference/Filesystem-API.html#filesystem-api) for more details.
For instance, to store data persistently between page reloads, one could mount
a folder with the
[IDBFS file system](https://emscripten.org/docs/api_reference/Filesystem-API.html#filesystem-api-idbfs)

```js
let mountDir = "/mnt";
pyodide.FS.mkdir(mountDir);
pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, { root: "." }, mountDir);
```

If you are using Node.js you can access the native file system by mounting `NODEFS`.

```js
let mountDir = "/mnt";
pyodide.FS.mkdir(mountDir);
pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: "." }, mountDir);
pyodide.runPython("import os; print(os.listdir('/mnt'))");
// ==> The list of files in the Node working directory
```

(nativefs-api)=

# (Experimental) Using the native file system in the browser

You can access the native file system from the browser using the
[File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API).

```{admonition} This is experimental
:class: warning

The File System Access API is only supported in Chromium based browsers: Chrome and Edge (as of 2022/08/18).
```

## Mounting a directory

Pyodide provides an API {js:func}`pyodide.mountNativeFS` which mounts a
{js:class}`FileSystemDirectoryHandle` into the Pyodide Python file system.

```js
const dirHandle = await showDirectoryPicker();

if ((await dirHandle.queryPermission({ mode: "readwrite" })) !== "granted") {
  if (
    (await dirHandle.requestPermission({ mode: "readwrite" })) !== "granted"
  ) {
    throw Error("Unable to read and write directory");
  }
}

const nativefs = await pyodide.mountNativeFS("/mount_dir", dirHandle);

pyodide.runPython(`
  import os
  print(os.listdir('/mount_dir'))
`);
```

## Synchronizing changes to native file system

Due to browser limitations, the changes in the mounted file system
is not synchronized by default. In order to persist any operations
to an native file system, you must call

```js
// nativefs is the returned from: await pyodide.mountNativeFS('/mount_dir', dirHandle)
pyodide.runPython(`
  with open('/mount_dir/new_file.txt', 'w') as f:
    f.write("hello");
`);

// new_file.txt does not exist in native file system

await nativefs.syncfs();

// new_file.txt will now exist in native file system
```

or

```js
pyodide.FS.syncfs(false, callback_func);
```
