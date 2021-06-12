import ast
import asyncio
from codeop import Compile, CommandCompiler, _features, PyCF_DONT_IMPLY_DEDENT  # type: ignore
from contextlib import (
    contextmanager,
    redirect_stdout,
    redirect_stderr,
    ExitStack,
)
from contextlib import _RedirectStream  # type: ignore
import rlcompleter
import platform
import sys
import traceback
from typing import Optional, Callable, Any, List, Tuple


from ._base import should_quiet, CodeRunner

# this import can fail when we are outside a browser (e.g. for tests)
try:
    from pyodide_js import loadPackagesFromImports as _load_packages_from_imports
    from asyncio import ensure_future
except ImportError:
    from asyncio import Future

    def ensure_future(co):  # type: ignore
        fut = Future()
        try:
            co.send(None)
        except StopIteration as v:
            result = v.args[0] if v.args else None
            fut.set_result(result)
        except BaseException as e:
            fut.set_exception(e)
        else:
            raise Exception("coroutine didn't finish in one pass")
        return fut

    async def _load_packages_from_imports(*args):
        pass


__all__ = ["repr_shorten", "BANNER"]


def _banner():
    """A banner similar to the one printed by the real Python interpreter."""
    # copied from https://github.com/python/cpython/blob/799f8489d418b7f9207d333eac38214931bd7dcc/Lib/code.py#L214
    cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
    version = platform.python_version()
    build = f"({', '.join(platform.python_build())})"
    return f"Python {version} {build} on WebAssembly VM\n{cprt}"


BANNER = _banner()
del _banner


class redirect_stdin(_RedirectStream):
    _stream = "stdin"


class _WriteStream:
    """A utility class so we can specify our own handlers for writes to sdout, stderr"""

    def __init__(self, write_handler, name=None):
        self.write_handler = write_handler
        self.name = name

    def write(self, text):
        self.write_handler(text)

    def flush(self):
        pass


class _ReadStream:
    """A utility class so we can specify our own handler for reading from stdin"""

    def __init__(self, read_handler, name=None):
        self.read_handler = read_handler
        self.name = name

    def readline(self, n=-1):
        return self.read_handler(n)

    def flush(self):
        pass


class MyCompile(Compile):
    """Instances of this class behave much like the built-in compile
    function, but if one is used to compile text containing a future
    statement, it "remembers" and compiles all subsequent program texts
    with the statement in force."""

    def __init__(
        self,
        *,
        return_mode="last_expr",
        quiet_trailing_semicolon=True,
        flags=0x0,
    ):
        super().__init__()
        self.flags |= flags
        self.return_mode = return_mode
        self.quiet_trailing_semicolon = quiet_trailing_semicolon

    def __call__(self, source, filename, symbol) -> CodeRunner:  # type: ignore
        return_mode = self.return_mode
        if self.quiet_trailing_semicolon and should_quiet(source):
            return_mode = None
        code_runner = CodeRunner(
            source,
            mode="single",
            filename=filename,
            return_mode=return_mode,
            flags=self.flags,
        ).compile()
        for feature in _features:
            if code_runner.code.co_flags & feature.compiler_flag:
                self.flags |= feature.compiler_flag
        return code_runner


class MyCommandCompiler(CommandCompiler):
    """Instances of this class have __call__ methods identical in
    signature to compile_command; the difference is that if the
    instance compiles program text containing a __future__ statement,
    the instance 'remembers' and compiles all subsequent program texts
    with the statement in force."""

    def __init__(
        self,
        *,
        return_mode="last_expr",
        quiet_trailing_semicolon=True,
        flags=0x0,
    ):
        self.compiler = MyCompile(
            return_mode=return_mode,
            quiet_trailing_semicolon=quiet_trailing_semicolon,
            flags=flags,
        )

    def __call__(self, source, filename="<input>", symbol="single") -> CodeRunner:  # type: ignore
        return super().__call__(source, filename, symbol)  # type: ignore


class InteractiveConsole:
    """Interactive Pyodide console

    Base implementation for an interactive console that manages
    stdout/stderr redirection. Since packages are loaded before running
    code, :any:`InteractiveConsole.runcode` returns a JS promise.

    ``self.stdout_callback`` and ``self.stderr_callback`` can be overloaded.

    Parameters
    ----------
    locals
        Namespace to evaluate code.
    stdout_callback
        Function to call at each ``sys.stdout`` flush.
    stderr_callback
        Function to call at each ``sys.stderr`` flush.
    persistent_stream_redirection
        Whether or not the std redirection should be kept between calls to
        ``runcode``.
    """

    def __init__(
        self,
        locals: Optional[dict] = None,
        *,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        stdin_callback: Optional[Callable[[str], None]] = None,
        persistent_stream_redirection: bool = False,
        filename: str = "<console>",
    ):
        if locals is None:
            locals = {"__name__": "__console__", "__doc__": None}
        self.locals = locals
        self._stdout = None
        self._stderr = None
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self.stdin_callback = stdin_callback
        self.filename = filename
        self.resetbuffer()
        self._lock = asyncio.Lock()
        self._streams_redirected = False
        self._stream_generator = None  # track persistent stream redirection
        if persistent_stream_redirection:
            self.persistent_redirect_streams()
        self._completer = rlcompleter.Completer(self.locals)  # type: ignore
        # all nonalphanums except '.'
        # see https://github.com/python/cpython/blob/a4258e8cd776ba655cc54ba54eaeffeddb0a267c/Modules/readline.c#L1211
        self.completer_word_break_characters = (
            """ \t\n`~!@#$%^&*()-=+[{]}\\|;:'\",<>/?"""
        )
        self.output_truncated_text = "\\n[[;orange;]<long output truncated>]\\n"
        self.compile = MyCommandCompiler(flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT | PyCF_DONT_IMPLY_DEDENT)  # type: ignore

    def persistent_redirect_streams(self):
        """Redirect stdin/stdout/stderr persistently"""
        if self._stream_generator:
            return
        self._stream_generator = self._stdstreams_redirections_inner()
        next(self._stream_generator)  # trigger stream redirection
        # streams will be reverted to normal when self._stream_generator is destroyed.

    def persistent_restore_streams(self):
        """Restore stdin/stdout/stderr if they have been persistently redirected"""
        # allowing _stream_generator to be garbage collected restores the streams
        self._stream_generator = None

    @contextmanager
    def redirect_streams(self):
        """A context manager to redirect standard streams.

        This supports nesting."""
        yield from self._stdstreams_redirections_inner()

    def _stdstreams_redirections_inner(self):
        """This is the generator which implements redirect_streams and the stdstreams_redirections"""
        # already redirected?
        if self._streams_redirected:
            yield
            return
        redirects = []
        if self.stdout_callback:
            redirects.append(
                redirect_stdout(
                    _WriteStream(self.stdout_callback, name=sys.stdout.name)
                )
            )
        if self.stderr_callback:
            redirects.append(
                redirect_stderr(
                    _WriteStream(self.stderr_callback, name=sys.stderr.name)
                )
            )
        if self.stdin_callback:
            redirects.append(
                redirect_stdin(_ReadStream(self.stdin_callback, name=sys.stdin.name))
            )
        try:
            self._streams_redirected = True
            with ExitStack() as stack:
                for redirect in redirects:
                    stack.enter_context(redirect)
                yield
        finally:
            self._streams_redirected = False

    def flush_all(self):
        """Force stdout/stderr flush."""
        with self.redirect_streams():
            sys.stdout.flush()
            sys.stderr.flush()

    def runsource(self, source: str, filename: str = "<input>", symbol: str = "single"):
        """Compile and run some source in the interpreter."""
        try:
            code = self.compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            # Case 1
            return ["syntax-error", self.formatsyntaxerror(filename)]

        if code is None:
            # Case 2
            return ["incomplete", None]

        return ["valid", ensure_future(self.runcode(source, code))]

    async def runcode(self, source: str, code: CodeRunner):
        """Execute a code object.

        When an exception occurs, self.showtraceback() is called to
        display a traceback.  All exceptions are caught except
        SystemExit, which is reraised.

        A note about KeyboardInterrupt: this exception may occur
        elsewhere in this code, and may not always be caught.  The
        caller should be prepared to deal with it.
        """
        await _load_packages_from_imports(source)
        async with self._lock:
            with self.redirect_streams():
                try:
                    return ["success", await code.run_async(self.locals)]
                except BaseException:
                    return ["exception", self.formattraceback()]
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()

    def formatsyntaxerror(self, filename=None):
        """Display the syntax error that just occurred.

        This doesn't display a stack trace because there isn't one.
        """
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        return "".join(traceback.format_exception_only(type, value))

    def formattraceback(self):
        """Display the exception that just occurred."""
        sys.last_type, sys.last_value, last_tb = ei = sys.exc_info()
        sys.last_traceback = last_tb
        try:
            return "".join(
                traceback.format_exception(ei[0], ei[1], last_tb.tb_next.tb_next)
            )
        finally:
            last_tb = ei = None

    def resetbuffer(self):
        """Reset the input buffer."""
        self.buffer = []

    def push(self, line: str):
        """Push a line to the interpreter.

        The line should not have a trailing newline; it may have
        internal newlines.  The line is appended to a buffer and the
        interpreter's runsource() method is called with the
        concatenated contents of the buffer as source.  If this
        indicates that the command was executed or invalid, the buffer
        is reset; otherwise, the command is incomplete, and the buffer
        is left as it was after the line was appended.  The return
        value is 1 if more input is required, 0 if the line was dealt
        with in some way (this is the same as runsource()).

        """
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        result = self.runsource(source, self.filename)
        if result[0] != "incomplete":
            self.resetbuffer()
        return result

    def complete(self, source: str) -> Tuple[List[str], int]:
        """Use CPython's rlcompleter to complete a source from local namespace.

        You can use ``completer_word_break_characters`` to get/set the
        way ``source`` is splitted to find the last part to be completed.

        Parameters
        ----------
        source
            The source string to complete at the end.

        Returns
        -------
        completions
            A list of completion strings.
        start
            The index where completion starts.

        Examples
        --------
        >>> shell = InteractiveConsole()
        >>> shell.complete("str.isa")
        (['str.isalnum(', 'str.isalpha(', 'str.isascii('], 0)
        >>> shell.complete("a = 5 ; str.isa")
        (['str.isalnum(', 'str.isalpha(', 'str.isascii('], 8)
        """
        start = max(map(source.rfind, self.completer_word_break_characters)) + 1
        source = source[start:]
        if "." in source:
            completions = self._completer.attr_matches(source)  # type: ignore
        else:
            completions = self._completer.global_matches(source)  # type: ignore
        return completions, start

    def display(self, value):
        if value is None:
            return
        print(repr_shorten(value, separator=self.output_truncated_text))


def repr_shorten(
    value: Any, limit: int = 1000, split: Optional[int] = None, separator: str = "..."
):
    """Compute the string representation of ``value`` and shorten it
    if necessary.

    If it is longer than ``limit`` then return the firsts ``split``
    characters and the last ``split`` characters seperated by '...'.
    Default value for ``split`` is `limit // 2`.
    """
    if split is None:
        split = limit // 2
    text = repr(value)
    if len(text) > limit:
        text = f"{text[:split]}{separator}{text[-split:]}"
    return text
