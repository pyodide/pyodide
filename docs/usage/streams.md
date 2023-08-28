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
    with pytest.raises(OSError, match="I/O error"):
        input()
`);
```

### Set the default behavior

You can set the default behavior by calling `pyodide.setStdin()` with no
arguments. In Node the default behavior is to read directly from Node's standard
input. In the browser, the default is the same as
`pyodide.setStdin({ stdin: () => prompt() })`.

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
  constructor(fd) {
    this.fd = fd;
    this.isatty = tty.isatty(fd);
  }

  read(buffer) {
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

As with stdin, `pyodide.setStdout()` sets the default behavior. In node, this is
to write directly to `process.stdout`. In the browser, the default is as if you
wrote
`setStdout({batched: (str) => console.log(str)})`
see below.

### A batched handler

A batched handler is the easiest standard out handler to implement but it is
also the coarsest. It is intended to use with APIs like `console.log` that don't
understand partial lines of text or for quick and dirty code.

The batched handler receives a string which is either:

1. a complete line of text with the newline removed or
2. a partial line of text that was flushed.

For instance after:

```py
print("hello!")
import sys
print("partial line", end="")
sys.stdout.flush()
```

the batched handler is called with `"hello!"` and then with `"partial line"`.
Note that there is no indication that `"hello!"` was a complete line of text and
`"partial line"` was not.

### A raw handler

A raw handler receives the output one character code at a time. This is neither
very convenient nor very efficient. It is present primarily for backwards
compatibility reasons.

For example, the following code:

```py
print("h")
import sys
print("p ", end="")
print("l", end="")
sys.stdout.flush()
```

will call the raw handler with the sequence of bytes:

```py
0x68 - h
0x0A - newline
0x70 - p
0x20 - space
0x6c - l
```

### A write handler

A write handler takes a `Uint8Array` as an argument and is supposed to write the
data in this buffer to standard output and return the number of bytes written.
For example, the following class can be used to write to a Node file descriptor:

```js
const fs = require("fs");
const tty = require("tty");
class NodeWriter {
  constructor(fd) {
    this.fd = fd;
    this.isatty = tty.isatty(fd);
  }

  write(buffer) {
    return fs.writeSync(this.fd, buffer);
  }
}
```

Using it as follows redirects output from Pyodide to `out.txt`:

```js
const fd = fs.openSync("out.txt", "w");
py.setStdout(new NodeWriter(fd));
```

Or the following gives the default behavior:

```js
const fd = fs.openSync("out.txt", "w");
py.setStdout(new NodeWriter(process.stdout.fd));
```

### isatty

As with `stdin`, is possible to control whether or not
{py:meth}`sys.stdout.isatty() <io.IOBase.isatty>` returns true with the `isatty`
option. You cannot combine `isatty: true` with a batched handler.
