(streams)=

# Redirecting standard streams

Pyodide has three functions {js:func}`pyodide.setStdin`,
{js:func}`pyodide.setStdout`, and {js:func}`pyodide.setStderr` that change the
behavior of reading from {py:data}`~sys.stdin` and writing to {py:data}`~sys.stdout` and
{py:data}`~sys.stderr` respectively.

## Standard Input

{js:func}`pyodide.setStdin` sets the standard in handler. There are several
different ways to do this depending on the options passed to `setStdin`.

### Always raise IO Error

If we pass `{error: true}`, any read from stdin raises an I/O error.

```js
pyodide.setStdin({ error: true });
pyodide.runPython(`
    with pytest.raises(OsError, match="I/O error"):
        input()
`);
```

### A stdin handler

We can pass the options `{stdin, isatty}`. `stdin` should be a
zero-argument function which should return one of:

1. A string which represents a full line of text (it will have a newline
   appended if it does not already end in one).
2. An array buffer or Uint8Array containing utf8 encoded characters
3. A number between 0 and 255 which indicates one byte of input
4. `undefined` which indicates EOF.

`isatty` is a boolean which
indicates whether `sys.stdin.isatty()` should return `true` or `false`.

For example, the following class plays back a list of results.

```js
class StdinHandler {
  constructor(results, isatty) {
    this.results = results;
    this.isatty = isatty;
    this.idx = 0;
  }

  stdin() {
    return this.results[this.idx++];
  }
}
```

Here's it in use:

```pyodide
pyodide.setStdin(
  new StdinHandler(["a", "bcd", "efg"], true /* isatty should be true */),
);
pyodide.runPython(`
    import sys
    assert sys.stdin.isatty() # returns true as we requested
    # input plays back the three strings we gave:
    assert input() == "a"
    assert input() == "bcd"
    assert input() == "efg"
    # after this, further attempts to read from stdin will return undefined which
    # indicates end of file
    with pytest.raises(EOFError, match="EOF when reading a line"):
        input()
`);
```

Note that the `input()` function automatically reads a line of text and
removes the trailing newline. If we use `sys.stdin.read` we see that newlines
have been appended to strings that don't end in a newline:

```pyodide
pyodide.setStdin(
  new StdinHandler(["a", "bcd\n", "efg", undefined, "h", "i"], true),
);
pyodide.runPython(`
    import sys
    assert sys.stdin.read() == "a\nbcd\nefg\n"
    assert sys.stdin.read() == "h\ni\n"
`);
```

Instead of strings we can return the list of utf8 bytes for the input:

```pyodide
pyodide.setStdin(
  new StdinHandler(
    [0x61 /* a */, 0x0a /* \n */, 0x62 /* b */, 0x63 /* c */],
    true,
  ),
);
pyodide.runPython(`
    assert input() == "a"
    assert input() == "bc"
`);
```

Or we can return a `Uint8Array` with the utf8-encoded text that we wish to
render:

```pyodide
pyodide.setStdin(
  new StdinHandler([new Uint8Array([0x61, 0x0a, 0x62, 0x63])], true),
);
pyodide.runPython(`
    assert input() == "a"
    assert input() == "bc"
`);
```

### A read handler

A read handler takes a `Uint8Array` as an argument and is supposed to place
the data into this buffer and return the number of bytes read. This is useful in
Node. For example, the following class can be used to read from a Node file
descriptor:

```js
const fs = require("fs");
const tty = require("tty");
class NodeReader {
  fd: number;
  isatty: boolean;

  constructor(fd: number) {
    this.fd = fd;
    this.isatty = tty.isatty(fd);
  }

  read(buffer: Uint8Array): number {
    return fs.readSync(this.fd, buffer);
  }
}
```

For instance to set stdin to read from a file called `input.txt`, we can do the
following:

```js
const fd = fs.openSync("input.txt", "r");
py.setStdin(new NodeReader(fd));
```

Or we can read from node's stdin (the default behavior) as follows:

```js
fd = fs.openSync("/dev/stdin", "r");
py.setStdin(new NodeReader(fd));
```

## Standard Out / Standard Error

`setStdout({batched?, raw?, isatty?})` sets the standard out handler and
similarly `setStderr` (same arguments) sets the stdandard error handler. If a
`raw` handler is provided then the handler is called with a `number` for each
byte of the output to stdout. The handler is expected to deal with this in
whatever way it prefers. `isatty` again controls whether {py:func}`isatty(stdout) <os.isatty>`
returns `true` or `false`.

On the other hand, a `batched` handler is only called with complete lines of
text (or when the output is flushed). A `batched` handler cannot have `isatty`
set to `true` because it is impossible to use such a handler to make something
behave like a tty.

Passing neither `raw` nor `batched` sets the default behavior. In Node the
default behavior is to write directly to {js:data}`process.stdout` and
{js:data}`process.stderr` (in this case `isatty` depends on whether
{js:data}`process.stdout` and {js:data}`process.stderr` are ttys). In browser,
the default behavior is achieved with `pyodide.setStdout({batched: console.log})`
and `pyodide.setStderr({batched: console.warn})`.

The arguments `stdin`, `stdout`, and `stderr` to `loadPyodide` provide a
diminished amount of control compared to `setStdin`, `setStdout`, and
`setStderr`. They all set `isatty` to `false` and use batched processing for
`setStdout` and `setStderr`. In most cases, nothing is written or read to any of
these streams while Pyodide is starting, so if you need the added flexibility
you can wait until Pyodide is loaded and then use the `pyodide.setStdxxx` apis.
