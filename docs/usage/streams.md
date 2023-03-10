(streams)=

# Redirecting standard streams

Pyodide has three functions {js:func}`pyodide.setStdin`,
{js:func}`pyodide.setStdout`, and {js:func}`pyodide.setStderr` that change the
behavior of reading from {py:data}`~sys.stdin` and writing to {py:data}`~sys.stdout` and
{py:data}`~sys.stderr` respectively.

`setStdin({stdin?, isatty?, error?})` takes a function which should take zero
arguments and return either a string or an ArrayBufferView of information read
from stdin. The `isatty` argument signals whether {py:func}`isatty(stdin) <os.isatty>` should be true
or false. If you pass `error: true` then reading from stdin will return an
error. If `setStdin` is called with no arguments, the default value is restored.
In Node the default behavior is to read from {js:data}`process.stdin` and in the browser
it is to throw an error.

`setStdout({batched?, raw?, isattty?})` sets the standard out handler and
similarly `setStderr` (same arguments) sets the stdandard error handler. If a
`raw` handler is provided then the handler is called with a `number` for each
byte of the output to stdout. The handler is expected to deal with this in
whatever way it prefers. `isattty` again controls whether {py:func}`isatty(stdout) <os.isatty>`
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
