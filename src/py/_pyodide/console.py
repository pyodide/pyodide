import ast
import asyncio
from asyncio import ensure_future, Future
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
from tokenize import TokenError
import traceback
from typing import Literal
from typing import (
    Optional,
    Callable,
    Any,
    List,
    Tuple,
    Union,
    Tuple,
)

from _pyodide._base import should_quiet, CodeRunner

__all__ = ["repr_shorten", "BANNER", "Console", "PyodideConsole", "ConsoleFuture"]


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

    def isatty(self) -> bool:
        return True


class _ReadStream:
    """A utility class so we can specify our own handler for reading from stdin"""

    def __init__(self, read_handler, name=None):
        self.read_handler = read_handler
        self.name = name

    def readline(self, n=-1):
        return self.read_handler(n)

    def flush(self):
        pass

    def isatty(self) -> bool:
        return True


class _Compile(Compile):
    """Compile code with CodeRunner, and remember future imports

    Instances of this class behave much like the built-in compile function,
    but if one is used to compile text containing a future statement, it
    "remembers" and compiles all subsequent program texts with the statement in
    force. It uses CodeRunner instead of the built in compile.
    """

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
        try:
            if self.quiet_trailing_semicolon and should_quiet(source):
                return_mode = None
        except (TokenError, SyntaxError):
            # Invalid code, let the Python parser throw the error later.
            pass

        code_runner = CodeRunner(
            source,
            mode=symbol,
            filename=filename,
            return_mode=return_mode,
            flags=self.flags,
        ).compile()
        for feature in _features:
            if code_runner.code.co_flags & feature.compiler_flag:
                self.flags |= feature.compiler_flag
        return code_runner


class _CommandCompiler(CommandCompiler):
    """Compile code with CodeRunner, and remember future imports, return None if
    code is incomplete.

    Instances of this class have __call__ methods identical in signature to
    compile; the difference is that if the instance compiles program text
    containing a __future__ statement, the instance 'remembers' and compiles all
    subsequent program texts with the statement in force.

    If the source is determined to be incomplete, will suppress the SyntaxError
    and return ``None``.
    """

    def __init__(
        self,
        *,
        return_mode="last_expr",
        quiet_trailing_semicolon=True,
        flags=0x0,
    ):
        self.compiler = _Compile(
            return_mode=return_mode,
            quiet_trailing_semicolon=quiet_trailing_semicolon,
            flags=flags,
        )

    def __call__(self, source, filename="<console>", symbol="single") -> Optional[CodeRunner]:  # type: ignore
        return super().__call__(source, filename, symbol)  # type: ignore


INCOMPLETE: Literal["incomplete"] = "incomplete"
SYNTAX_ERROR: Literal["syntax-error"] = "syntax-error"
COMPLETE: Literal["complete"] = "complete"


class ConsoleFuture(Future):
    """A future with extra fields used as the return value for :any:`Console` apis.

    Attributes
    ----------
    syntax_check : str
        One of ``"incomplete"``, ``"syntax-error"``, or ``"complete"``. If the value is
        ``"incomplete"`` then the future has already been resolved with result equal to
        ``None``. If the value is ``"syntax-error"``, the ``Future`` has already been
        rejected with a ``SyntaxError``. If the value is ``"complete"``, then the input
        complete and syntactically correct.

    formatted_error : str
        If the ``Future`` is rejected, this will be filled with a formatted version of
        the code. This is a convenience that simplifies code and helps to avoid large
        memory leaks when using from JavaScript.

    """

    def __init__(
        self,
        syntax_check: Union[
            Literal["incomplete"], Literal["syntax-error"], Literal["complete"]
        ],
    ):
        super().__init__()
        self.syntax_check: Union[
            Literal["incomplete"], Literal["syntax-error"], Literal["complete"]
        ] = syntax_check
        self.formatted_error: Optional[str] = None


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

    stdin_callback : ``Callable[[str], None]``
        Function to call at each read from ``sys.stdin``. Defaults to ``None``.

    stdout_callback : ``Callable[[str], None]``
        Function to call at each write to ``sys.stdout``. Defaults to ``None``.

    stderr_callback : ``Callable[[str], None]``
        Function to call at each write to ``sys.stderr``. Defaults to ``None``.

    persistent_stream_redirection : ``bool``
        Should redirection of standard streams be kept between calls to :any:`runcode <Console.runcode>`?
        Defaults to ``False``.

    filename : ``str``
        The file name to report in error messages. Defaults to ``<console>``.

    Attributes
    ----------
        globals : ``Dict[str, Any]``
            The namespace used as the global

        stdin_callback : ``Callback[[str], None]``
            Function to call at each read from ``sys.stdin``.

        stdout_callback : ``Callback[[str], None]``
            Function to call at each write to ``sys.stdout``.

        stderr_callback : ``Callback[[str], None]``
            Function to call at each write to ``sys.stderr``.

        buffer : ``List[str]``
            The list of strings that have been :any:`pushed <Console.push>` to the console.

        completer_word_break_characters : ``str``
            The set of characters considered by :any:`complete <Console.complete>` to be word breaks.
    """

    def __init__(
        self,
        globals: Optional[dict] = None,
        *,
        stdin_callback: Optional[Callable[[str], None]] = None,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        persistent_stream_redirection: bool = False,
        filename: str = "<console>",
    ):
        if globals is None:
            globals = {"__name__": "__console__", "__doc__": None}
        self.globals = globals
        self._stdout = None
        self._stderr = None
        self.stdin_callback = stdin_callback
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
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
        self._compile = _CommandCompiler(flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)  # type: ignore

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
        if self.stdin_callback:
            stdin_name = getattr(sys.stdin, "name", "<stdin>")
            stdin_stream = _ReadStream(self.stdin_callback, name=stdin_name)
            redirects.append(redirect_stdin(stdin_stream))
        if self.stdout_callback:
            stdout_name = getattr(sys.stdout, "name", "<stdout>")
            stdout_stream = _WriteStream(self.stdout_callback, name=stdout_name)
            redirects.append(redirect_stdout(stdout_stream))
        if self.stderr_callback:
            stderr_name = getattr(sys.stderr, "name", "<stderr>")
            stderr_stream = _WriteStream(self.stderr_callback, name=stderr_name)
            redirects.append(redirect_stderr(stderr_stream))
        try:
            self._streams_redirected = True
            with ExitStack() as stack:
                for redirect in redirects:
                    stack.enter_context(redirect)
                yield
        finally:
            self._streams_redirected = False

    def runsource(self, source: str, filename: str = "<console>") -> ConsoleFuture:
        """Compile and run source code in the interpreter.

        Returns
        -------
            :any:`ConsoleFuture`

        """
        try:
            code = self._compile(source, filename, "single")
        except (OverflowError, SyntaxError, ValueError) as e:
            # Case 1
            if e.__traceback__:
                traceback.clear_frames(e.__traceback__)
            res = ConsoleFuture(SYNTAX_ERROR)
            res.set_exception(e)
            res.formatted_error = self.formatsyntaxerror(e)
            return res

        if code is None:
            res = ConsoleFuture(INCOMPLETE)
            res.set_result(None)
            return res

        res = ConsoleFuture(COMPLETE)

        def done_cb(fut):
            nonlocal res
            exc = fut.exception()
            if exc:
                res.formatted_error = self.formattraceback(exc)
                res.set_exception(exc)
                exc = None
            else:
                res.set_result(fut.result())
            res = None  # type: ignore

        ensure_future(self.runcode(source, code)).add_done_callback(done_cb)
        return res

    async def runcode(self, source: str, code: CodeRunner) -> Any:
        """Execute a code object and return the result."""
        async with self._lock:
            with self.redirect_streams():
                try:
                    return await code.run_async(self.globals)
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()

    def formatsyntaxerror(self, e: Exception) -> str:
        """Format the syntax error that just occurred.

        This doesn't include a stack trace because there isn't one. The actual
        error object is stored into `sys.last_value`.
        """
        sys.last_type = type(e)
        sys.last_value = e
        sys.last_traceback = None
        try:
            return "".join(traceback.format_exception_only(type(e), e))
        finally:
            e = None  # type: ignore

    def num_frames_to_keep(self, tb):
        keep_frames = False
        kept_frames = 0
        # Try to trim out stack frames inside our code
        for (frame, _) in traceback.walk_tb(tb):
            keep_frames = keep_frames or frame.f_code.co_filename == "<console>"
            keep_frames = keep_frames or frame.f_code.co_filename == "<exec>"
            if keep_frames:
                kept_frames += 1
        return kept_frames

    def formattraceback(self, e: Exception) -> str:
        """Format the exception that just occurred.

        The actual error object is stored into `sys.last_value`.
        """
        try:
            sys.last_type = type(e)
            sys.last_value = e
            sys.last_traceback = e.__traceback__
            nframes = self.num_frames_to_keep(e.__traceback__)
            return "".join(
                traceback.format_exception(type(e), e, e.__traceback__, -nframes)
            )
        finally:
            e = None  # type: ignore

    def push(self, line: str) -> ConsoleFuture:
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
        if result.syntax_check != INCOMPLETE:
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
