import contextlib
import traceback
from typing import Optional, Callable, Any, List, Tuple, CodeType
import code
import io
import sys
import platform
from contextlib import contextmanager, redirect_stdout, redirect_stderr, _RedirectStream
import rlcompleter
import asyncio
from ._base import eval_code, MyCommandCompiler
import ast
from asyncio import iscoroutine, Lock

class redirect_stdin(_RedirectStream):
    _stream = "stdin"

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


__all__ = ["InteractiveConsole", "repr_shorten"]

def _banner():
    """ A banner similar to the one printed by the real Python interpreter. """
    # copied from https://github.com/python/cpython/blob/799f8489d418b7f9207d333eac38214931bd7dcc/Lib/code.py#L214
    cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
    version = platform.python_version()
    build = f"({', '.join(platform.python_build())})"
    return f"Python {version} {build} on WebAssembly VM\n{cprt}"
BANNER = _banner()
del _banner

def complete(source: str, completer_word_break_characters = """ \t\n`~!@#$%^&*()-=+[{]}\\|;:'\",<>/?""") -> Tuple[List[str], int]:
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
    start = max(map(source.rfind, completer_word_break_characters)) + 1
    source = source[start:]
    if "." in source:
        completions = self._completer.attr_matches(source)  # type: ignore
    else:
        completions = self._completer.global_matches(source)  # type: ignore
    return completions, start

class WriteStream:
    """A utility class so we can specify our own handlers for writes to sdout, stderr"""

    def __init__(self, write_handler):
        self.write_handler = write_handler

    def write(self, text):
        self.write_handler(text)


class ReadStream:
    def __init__(self, read_handler):
        self.read_handler = read_handler

    def readline(self, n=-1):
        return self.read_handler(n)

class _CallbackBuffer(io.RawIOBase):
    """
    Internal _StdStream buffer that triggers flush callback.

    Parmeters
    ---------
    flush_callback
        Function to call at each flush.
    """

    def __init__(
        self, flush_callback: Callable[[str], None], name: Optional[str] = None
    ):
        self._flush_callback = flush_callback
        self.name = name

    def writable(self):
        return True

    def seekable(self):
        return False

    def isatty(self):
        return True

    def write(self, data):
        self._flush_callback(data.tobytes().decode())
        return len(data)

class _InteractiveConsoleWrapper(code.InteractiveConsole):
    """A wrapper around ``code.InteractiveConsole`` that passes extra information around.
    """
    def push(self, line, extra=None):
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
        more = self.runsource(source, self.filename, extra=extra) # <-- changed by adding "extra" argument
        if not more:
            self.resetbuffer()
        return more

    def runsource(self, source, filename="<input>", symbol="single", extra : Any = None):
        """Compile and run some source in the interpreter.

        Arguments are as for compile_command().

        One of several things can happen:

        1) The input is incorrect; compile_command() raised an
        exception (SyntaxError or OverflowError).  A syntax traceback
        will be printed by calling the showsyntaxerror() method.

        2) The input is incomplete, and more input is required;
        compile_command() returned None.  Nothing happens.

        3) The input is complete; compile_command() returned a code
        object.  The code is executed by calling self.runcode() (which
        also handles run-time exceptions, except for SystemExit).

        The return value is True in case 2, False in the other cases (unless
        an exception is raised).  The return value can be used to
        decide whether to use sys.ps1 or sys.ps2 to prompt the next
        line.

        """
        try:
            code = self.compile(source, filename, symbol) # <-- We could pass "extra" here if we wanted to...
        except (OverflowError, SyntaxError, ValueError):
            # Case 1
            self.showsyntaxerror(filename, extra) # <-- changed by adding "extra" argument
            return False

        if code is None:
            # Case 2
            return True

        # Case 3
        self.runcode(source, code, extra=extra) # <-- changed by adding "source" and "extra" arguments
        return False
    
    def runcode(self, source : str, code: CodeType, extra : Any = None) -> None:
        return super().runcode(code)


class InteractiveConsole(_InteractiveConsoleWrapper):
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
        Function to call at each ``sys.stdout`` flush. If absent, will use normal ``sys.stdout``.

    stderr_callback
        Function to call at each ``sys.stderr`` flush. If absent, will use existing ``sys.stderr``.

    persistent_stream_redirection
        Whether or not the std redirection should be kept between calls to
        ``runcode``.
    """

    def __init__(
        self,
        locals: Optional[dict] = None,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        persistent_stream_redirection: bool = False,
    ):
        super().__init__(locals)
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self._streams_redirected = False
        if persistent_stream_redirection:
            # Redirect streams. We want the streams to be restored when we are
            # garbage collected so we just hold the reference to the generator
            # forever. When we are garbage collected, the generator will be
            # finalized and its finally block will restore the streams
            self._stream_generator = self._stdstreams_redirections_inner()
            next(self._stream_generator) # Cause stream setup
        self._lock = Lock()
        self._completer = rlcompleter.Completer(self.locals)  # type: ignore
        # all nonalphanums except '.'
        # see https://github.com/python/cpython/blob/a4258e8cd776ba655cc54ba54eaeffeddb0a267c/Modules/readline.c#L1211
        self.output_truncated_text = "\\n[[;orange;]<long output truncated>]\\n"
        self.compile = MyCommandCompiler(flag=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    @property
    def stdout_callback(self):
        return self._stdout_callback

    @property.setter
    def stdout_callback(self, v):
        if self._streams_redirected:
            raise RuntimeError("Trying to set stdout callback while streams are already redirected.")
        self._stdout_callback = v
        if v is not None:
            self.__stdout_callback = v
        else:
            self.__stdout_callback = None

    @property
    def stderr_callback(self):
        return self._stderr_callback

    @property.setter
    def stderr_callback(self, v):
        if self._streams_redirected:
            raise RuntimeError("Trying to set stderr callback while streams are already redirected.")
        self._stderr_callback = v
        if v is not None:
            self.__stderr_callback = v
        else:
            self.__stderr_callback = None

    @property
    def stdin_callback(self):
        return self._stderr_callback

    @property.setter
    def stdin_callback(self, v):
        if self._streams_redirected:
            raise RuntimeError("Trying to set stderr callback while streams are already redirected.")
        self._stdin_callback = v
        if v is not None:
            self.__stdin_callback = v
        else:
            self.__stdin_callback = None

    def _stdstreams_redirections_inner(self):
        """The point of this method is so that when  """
        # already redirected?
        if self._streams_redirected:
            yield
            return
        if self.__stdout_callback:
            stdout = WriteStream(self.__stdout_callback, name=sys.stdout.name)
        else:
            stdout = None
        if self.__stderr_callback:
            stderr = WriteStream(self.__stderr_callback, name=sys.stderr.name)
        if self.__stdin_callback:
            stdin = ReadStream(self.__stderr_callback, name=sys.stderr.name)

        try:
            self._streams_redirected = True
            with redirect_stdout(stdout), redirect_stderr(stderr), redirect_stdin(stdin):
                yield
        finally:
            self._streams_redirected = False


    @contextmanager
    def stdstreams_redirections(self):
        """Ensure std stream redirection.

        This supports nesting."""
        yield from self._stdstreams_redirections_inner()

    def runcode(self, source, code, extra):
        """Load imported packages then run code, async.

        To achieve nice result representation, the interactive console is fully
        implemented in Python. The interactive console api is synchronous, but
        we want to implement asynchronous package loading and top level await.

        Extra should contain a pair of futures:
        [syntax_check, ]
        """
        ensure_future(
            self.load_packages_and_run(source, code)
        )

    async def runcode_inner(source, code, extra):
        try:
            result = eval(code, globals, locals)
            if iscoroutine(result):
                result = await result
        except BaseException as e:
            raise e
        else:
            pass

    async def load_packages_and_run(self, run_complete, source, code, extra):
        # We can start fetching packages even if we're waiting on another code
        # block. (Probably won't help very often, not to mention that
        # loadPackages has its own lock.)
        await _load_packages_from_imports(source)
        async with self._lock:
            with self.stdstreams_redirections():
                self.runcode_inner(source, code, extra)
                sys.stdout.flush()
                sys.stderr.flush()
    
    def push_wrapped(self, line: str) -> bool:
        extra = []
        more = super().push(line, extra)
        if not more:
            pass


def repr_shorten(
    value: Any, limit: int = 1000, split: Optional[int] = None, separator: str = "\\n[[;orange;]<long output truncated>]\\n"
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

