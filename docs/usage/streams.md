(streams)=

# Redirecting standard streams

Pyodide has three functions {js:func}`pyodide.setStdin`,
{js:func}`pyodide.setStdout`, and {js:func}`pyodide.setStderr` that change the
behavior of reading from {py:data}`~sys.stdin` and writing to {py:data}`~sys.stdout` and
{py:data}`~sys.stderr` respectively.

## Standard Input

(streams-stdin)=

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

### Set the default behavior

You can set the default behavior by calling `pyodide.setStdin()` with no
arguments. In Node the default behavior is to read directly from Node's standard
input. In the browser, the default is the same as
`pyodide.setStdin({ error: true })`.

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
  constructor(results, options) {
    this.results = results;
    this.idx = 0;
    Object.assign(this, options);
  }

  stdin() {
    return this.results[this.idx++];
  }
}
```

Here it is in use:

```pyodide
pyodide.setStdin(
  new StdinHandler(["a", "bcd", "efg"]),
);
pyodide.runPython(`
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
  new StdinHandler(["a", "bcd\n", "efg", undefined, "h", "i"]),
);
pyodide.runPython(String.raw`
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
  new StdinHandler([new Uint8Array([0x61, 0x0a, 0x62, 0x63])]),
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

### isatty

It is possible to control whether or not {py:meth}`sys.stdin.isatty() <io.IOBase.isatty>`
returns true with the `isatty` option:

```pyodide
pyodide.setStdin(new StdinHandler([], {isatty: true}));
pyodide.runPython(`
    import sys
    assert sys.stdin.isatty() # returns true as we requested
`);
pyodide.setStdin(new StdinHandler([], {isatty: false}));
pyodide.runPython(`
  assert not sys.stdin.isatty() # returns false as we requested
`);
```

This will change the behavior of cli applications that behave differently in an
interactive terminal, for example pytest does this.

### Raising IO errors

To raise an IO error in either a `stdin` or `read` handler, you should throw an
IO error as follows:

```js
throw new pyodide.FS.ErrnoError(pyodide.ERRNO_CODES.EIO);
```

for instance, saying:

```js
pyodide.setStdin({
  read(buf) {
    throw new pyodide.FS.ErrnoError(pyodide.ERRNO_CODES.EIO);
  },
});
```

is the same as `pyodide.setStdin({error: true})`.

### Handling Keyboard interrupts

To handle a keyboard interrupt in an input handler, you should periodically call
{js:func}`pyodide.checkInterrupt`. For example, the following stdin handler
always raises a keyboard interrupt:

```js
const interruptBuffer = new Int32Array(new SharedArrayBuffer(4));
pyodide.setInterruptBuffer(interruptBuffer);
pyodide.setStdin({
  read(buf) {
    // Put signal into interrupt buffer
    interruptBuffer[0] = 2;
    // Call checkInterrupt to raise an error
    pyodide.checkInterrupt();
    console.log(
      "This code won't ever be executed because pyodide.checkInterrupt raises an error!",
    );
  },
});
```

For a more realistic example that handles reading stdin in a worker and also
keyboard interrupts, you might something like the following code:

```js
pyodide.setStdin({read(buf) {
  const timeoutMilliseconds = 100;
  while(true) {
    switch(Atomics.wait(stdinSharedBuffer, 0, 0, timeoutMilliseconds) {
      case "timed-out":
        // 100 ms passed but got no data, check for keyboard interrupt then return to waiting on data.
        pyodide.checkInterrupt();
        break;
      case "ok":
        // ... handle the data somehow
        break;
    }
  }
}});
```

See also {ref}`interrupting_execution`.

## Standard Out / Standard Error

(streams-stdout)=

{js:func}`pyodide.setStdout` and {js:func}`pyodide.setStderr` respectively set
the standard output and standard error handlers. These APIs are identical except
in their defaults, so we will only discuss the `pyodide.setStdout` except in
cases where they differ.

As with {js:func}`pyodide.setStdin`, there are quite a few different ways to set
the standard output handlers.

### Set the default behavior

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

Calling `setStdout` with no arguments sets the default behavior. In Node the
default behavior is to write directly to {js:data}`process.stdout` and
{js:data}`process.stderr` (in this case `isatty` depends on whether
{js:data}`process.stdout` and {js:data}`process.stderr` are ttys). In browser,
the default behavior is achieved with `pyodide.setStdout({batched:
console.log})` and `pyodide.setStderr({batched: console.warn})`.

The arguments `stdin`, `stdout`, and `stderr` to `loadPyodide` provide a
diminished amount of control compared to `setStdin`, `setStdout`, and
`setStderr`. They all set `isatty` to `false` and use batched processing for
`setStdout` and `setStderr`. In most cases, nothing is written or read to any of
these streams while Pyodide is starting, so if you need the added flexibility
you can wait until Pyodide is loaded and then use the `pyodide.setStdxxx` apis.
