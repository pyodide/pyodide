(file-system)=

# Dealing with Pyodide file system

Pyodide supports file system through [Emscripten File System API](https://emscripten.org/docs/api_reference/Filesystem-API.html#filesystem-api).
In JavaScript, Pyodide file system can be accessed through {any}`pyodide.FS`.

**Example: Reading from the file system**

```js
pyodide.runPython(`
  f = open("/hello.txt", "w")
  f.write("hello world!")
  f.close()
`);

let file = pyodide.FS.readFile("/hello.txt", { encoding: "utf-8" });
console.log(file);
```

**Example: Writing to the file system**

```js
let data = "hello world!";
pyodide.FS.writeFile("/hello.txt", data, { encoding: "utf-8" });
pyodide.runPython(`
  f = open("/hello.txt", "r")
  data = f.read()
  print(data)
`);
```

## Mounting a file system

The default file system of Pyodide is [MEMFS](https://emscripten.org/docs/api_reference/Filesystem-API.html#memfs),
which is a virtual file system saved in memory. The data saved in MEMFS will be lost when the page is reloaded.

To prevent that situation, you can mount other types of file systems.
Pyodide supports various file systems: `IDBFS`, `NODEFS`, `PROXYFS`, `WORKERFS`.
The implementations are available as members of {any}`pyodide.FS.filesystems`.
Note that each file system requires specific runtime environments.
See [Emscripten File System API](https://emscripten.org/docs/api_reference/Filesystem-API.html#filesystem-api) for the detail.

```js
let mountDir = "/mnt";
pyodide.FS.mkdir(mountDir);
pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, { root: "." }, mountDir);
```
