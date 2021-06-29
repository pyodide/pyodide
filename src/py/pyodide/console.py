import ast
import asyncio
from asyncio import ensure_future
from codeop import Compile, CommandCompiler, _features  # type: ignore
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
from typing import (
    Optional,
    Callable,
    Any,
    List,
    Tuple,
    Union,
    Tuple,
    Literal,
    Awaitable,
)

from ._base import should_quiet, CodeRunner

__all__ = ["repr_shorten", "BANNER", "Console", "PyodideConsole"]


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


class _CodeRunnerCompile(Compile):
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


class _CodeRunnerCommandCompiler(CommandCompiler):
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
        self.compiler = _CodeRunnerCompile(
            return_mode=return_mode,
            quiet_trailing_semicolon=quiet_trailing_semicolon,
            flags=flags,
        )

    def __call__(self, source, filename="<console>", symbol="single") -> CodeRunner:  # type: ignore
        return super().__call__(source, filename, symbol)  # type: ignore


RunCodeResult = Union[Tuple[Literal["exception"], str], Tuple[Literal["success"], Any]]
RunSourceResult = Union[
    Tuple[Literal["incomplete"], None],
    Tuple[Literal["syntax-error"], str],
    Tuple[Literal["complete"], Awaitable[RunCodeResult]],
]

INCOMPLETE: Literal["incomplete"] = "incomplete"
SYNTAX_ERROR: Literal["syntax-error"] = "syntax-error"
COMPLETE: Literal["complete"] = "complete"

SUCCESS: Literal["success"] = "success"
EXCEPTION: Literal["exception"] = "exception"


class Console:
    """Interactive Pyodide console

    An interactive console based on the Python standard library
    `code.InteractiveConsole` that manages stream redirections and asynchronous
    execution of the code.

    The stream callbacks can be modified directly as long as
    `persistent_stream_redirection` isn't in effect.

    Parameters
    ----------
    globals : ``dict``

        The global namespace in which to evaluate the code. Defaults to a new empty dictionary.

    stdout_callback : Callable[[str], None] Function to call at each write to
        ``sys.stdout``. Defaults to ``None``.

    stderr_callback : Callable[[str], None]

        Function to call at each write to ``sys.stderr``. Defaults to ``None``.

    stdin_callback : Callable[[str], None]

        Function to call at each read from ``sys.stdin``. Defaults to ``None``.

    persistent_stream_redirection : bool

        Should redirection of standard streams be kept between calls to :any:`runcode <Console.runcode>`?
        Defaults to ``False``.

    filename : str

        The file name to report in error messages. Defaults to ``<console>``.

    Attributes
    ----------
        globals : Dict[str, Any]

            The namespace used as the global

        stdout_callback : Callback[[str], None]

            Function to call at each write to ``sys.stdout``.

        stderr_callback : Callback[[str], None]

            Function to call at each write to ``sys.stderr``.

        stdin_callback : Callback[[str], None]

            Function to call at each read from ``sys.stdin``.

        buffer : List[str]

            The list of strings that have been :any:`pushed <Console.push>` to the console.

        completer_word_break_characters : str

            The set of characters considered by :any:`complete <Console.complete>` to be word breaks.
    """

    def __init__(
        self,
        globals: Optional[dict] = None,
        *,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        stdin_callback: Optional[Callable[[str], None]] = None,
        persistent_stream_redirection: bool = False,
        filename: str = "<console>",
    ):
        if globals is None:
            globals = {"__name__": "__console__", "__doc__": None}
        self.globals = globals
        self._stdout = None
        self._stderr = None
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self.stdin_callback = stdin_callback
        self.filename = filename
        self.buffer: List[str] = []
        self._lock = asyncio.Lock()
        self._streams_redirected = False
        self._stream_generator = None  # track persistent stream redirection
        if persistent_stream_redirection:
            self.persistent_redirect_streams()
        self._completer = rlcompleter.Completer(self.globals)  # type: ignore
        # all nonalphanums except '.'
        # see https://github.com/python/cpython/blob/a4258e8cd776ba655cc54ba54eaeffeddb0a267c/Modules/readline.c#L1211
        self.completer_word_break_characters = (
            """ \t\n`~!@#$%^&*()-=+[{]}\\|;:'\",<>/?"""
        )
        self._compile = _CodeRunnerCommandCompiler(flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)  # type: ignore

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

    def runsource(self, source: str, filename: str = "<console>") -> RunSourceResult:
        """Compile and run source code in the interpreter.

        Returns
        -------
            ``("incomplete", None)``
                The source string is incomplete.

            ``("syntax-error", message ꞉ str)``
                The source had a syntax error. ``message` is the formatted error
                message as returned by :any:`Console.formatsyntaxerror`.

            ``("complete", future ꞉ Future[RunCodeResult])``
                The source was complete and is being run. The ``Future`` will be
                resolved with the result of :any:`Console.runcode` when it is finished
                running.
        """
        try:
            code = self._compile(source, filename, "single")
        except (OverflowError, SyntaxError, ValueError):
            # Case 1
            return (SYNTAX_ERROR, self.formatsyntaxerror())

        if code is None:
            # Case 2
            return (INCOMPLETE, None)

        return (COMPLETE, ensure_future(self.runcode(source, code)))

    async def runcode(self, source: str, code: CodeRunner) -> "RunCodeResult":
        """Execute a code object.

        All exceptions are caught except SystemExit, which is reraised.

        Returns
        -------
            ``("success", result ꞉ Any)``
                The code executed successfully and returned ``result``.

            ``("exception", message ꞉ str)``
                An exception occurred. `message` is the result of calling
                :any:`Console.formattraceback`.
        """
        async with self._lock:
            with self.redirect_streams():
                try:
                    return (SUCCESS, await code.run_async(self.globals))
                except SystemExit:
                    raise
                except (Exception, KeyboardInterrupt):
                    return (EXCEPTION, self.formattraceback())
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()

    def formatsyntaxerror(self) -> str:
        """Format the syntax error that just occurred.

        This doesn't include a stack trace because there isn't one. The actual
        error object is stored into `sys.last_value`.
        """
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        try:
            return "".join(traceback.format_exception_only(type, value))
        finally:
            type = value = tb = None

    def formattraceback(self) -> str:
        """Format the exception that just occurred.

        The actual error object is stored into `sys.last_value`.
        """
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        trunc_tb = tb.tb_next.tb_next  # type: ignore
        try:
            return "".join(traceback.format_exception(type, value, trunc_tb))
        finally:
            type = value = tb = trunc_tb = None

    def push(self, line: str) -> "RunSourceResult":
        """Push a line to the interpreter.

        The line should not have a trailing newline; it may have internal
        newlines.  The line is appended to a buffer and the interpreter's
        runsource() method is called with the concatenated contents of the
        buffer as source.  If this indicates that the command was executed or
        invalid, the buffer is reset; otherwise, the command is incomplete, and
        the buffer is left as it was after the line was appended.

        The return value is the result of calling :any:`Console.runsource` on the current buffer
        contents.
        """
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        result = self.runsource(source, self.filename)
        if result[0] != "incomplete":
            self.buffer = []
        return result

    def complete(self, source: str) -> Tuple[List[str], int]:
        """Use Python's rlcompleter to complete the source string using the :any:`globals <Console.globals>` namespace.

        Finds last "word" in the source string and completes it with rlcompleter. Word
        breaks are determined by the set of characters in
        :any:`completer_word_break_characters <Console.completer_word_break_characters>`.

        Parameters
        ----------
        source : str
            The source string to complete at the end.

        Returns
        -------
        completions : List[str]
            A list of completion strings.
        start : int
            The index where completion starts.

        Examples
        --------
        >>> shell = Console()
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


class PyodideConsole(Console):
    """A subclass of :any:`Console` that uses :any:`pyodide.loadPackagesFromImports` before running the code."""

    async def runcode(self, source: str, code: CodeRunner) -> "RunCodeResult":
        """Execute a code object.

        All exceptions are caught except SystemExit, which is reraised.

        Returns
        -------
            The return value is a dependent sum type with the following possibilities:
            * `("success", result : Any)` -- the code executed successfully
            * `("exception", message : str)` -- An exception occurred. `message` is the
            result of calling :any:`Console.formattraceback`.
        """
        from pyodide_js import loadPackagesFromImports

        await loadPackagesFromImports(source)
        return await super().runcode(source, code)


def repr_shorten(
    value: Any, limit: int = 1000, split: Optional[int] = None, separator: str = "..."
) -> str:
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
