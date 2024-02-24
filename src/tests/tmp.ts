const root = await navigator.storage.getDirectory();
const handle = await root.getDirectoryHandle("dir", { create: true });

await pyodide.mountNativeFS("/mnt1/nativefs", handle);
assertThrowsAsync(
  async () => await pyodide.mountNativeFS("/mnt1/nativefs", handle),
  "Error",
  "path '/mnt1/nativefs' is already a file system mount point",
);

pyodide.FS.mkdirTree("/mnt2");
pyodide.FS.writeFile("/mnt2/nativefs", "contents");
assertThrowsAsync(
  async () => await pyodide.mountNativeFS("/mnt2/nativefs", handle),
  "Error",
  "path '/mnt2/nativefs' points to a file not a directory",
);

pyodide.FS.mkdirTree("/mnt3/nativefs");
pyodide.FS.writeFile("/mnt3/nativefs/a.txt", "contents");
assertThrowsAsync(
  async () => await pyodide.mountNativeFS("/mnt3/nativefs", handle),
  "Error",
  "directory '/mnt3/nativefs' is not empty",
);

const [r1, r2] = await allSettled([
  pyodide.mountNativeFS("/mnt4/nativefs", handle),
  pyodide.mountNativeFS("/mnt4/nativefs", handle),
]);
assert(() => r1.status === "fulfilled");
assert(() => r2.status === "rejected");
assert(
  () =>
    r2.reason.message === "path '/mount4' is already a directory mount point",
);
