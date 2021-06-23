import ast
import asyncio
import code
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


from ._base import eval_code_async

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


class _InteractiveConsole(code.InteractiveConsole):
    """Interactive Pyodide console

    Base implementation for an interactive console that manages
    stdout/stderr redirection. Since packages are loaded before running
    code, :any:`_InteractiveConsole.runcode` returns a JS promise.

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
    ):
        super().__init__(locals)
        self._stdout = None
        self._stderr = None
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self.stdin_callback = stdin_callback
        self._streams_redirected = False
        self._stream_generator = None  # track persistent stream redirection
        if persistent_stream_redirection:
            self.persistent_redirect_streams()
        self.run_complete: asyncio.Future = asyncio.Future()
        self.run_complete.set_result(None)
        self._completer = rlcompleter.Completer(self.locals)  # type: ignore
        # all nonalphanums except '.'
        # see https://github.com/python/cpython/blob/a4258e8cd776ba655cc54ba54eaeffeddb0a267c/Modules/readline.c#L1211
        self.completer_word_break_characters = (
            """ \t\n`~!@#$%^&*()-=+[{]}\\|;:'\",<>/?"""
        )
        self.output_truncated_text = "\\n[[;orange;]<long output truncated>]\\n"
        self.compile.compiler.flags |= ast.PyCF_ALLOW_TOP_LEVEL_AWAIT  # type: ignore

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

    def runsource(self, *args, **kwargs):
        """Force streams redirection.

        Syntax errors are not thrown by :any:`_InteractiveConsole.runcode` but
        here in :any:`_InteractiveConsole.runsource`. This is why we force
        redirection here since doing twice is not an issue.
        """

        with self.redirect_streams():
            return super().runsource(*args, **kwargs)

    def runcode(self, code):
        """Load imported packages then run code, async.

        To achieve nice result representation, the interactive console is fully
        implemented in Python. The interactive console api is synchronous, but
        we want to implement asynchronous package loading and top level await.
        Thus, instead of blocking like it normally would, this this function
        sets the future ``self.run_complete``. If you need the result of the
        computation, you should await for it.
        """
        source = "\n".join(self.buffer)
        self.run_complete = ensure_future(
            self.load_packages_and_run(self.run_complete, source)
        )

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

    async def load_packages_and_run(self, run_complete, source):
        try:
            await run_complete
        except BaseException:
            # Throw away old error
            pass
        with self.redirect_streams():
            await _load_packages_from_imports(source)
            try:
                result = await eval_code_async(
                    source, self.locals, filename="<console>"
                )
            except BaseException as e:
                nframes = self.num_frames_to_keep(e.__traceback__)
                traceback.print_exception(type(e), e, e.__traceback__, -nframes)
                raise e
            else:
                self.display(result)
            # in CPython's REPL, flush is performed
            # by input(prompt) at each new prompt ;
            # since we are not using input, we force
            # flushing here
            self.flush_all()
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
        >>> shell = _InteractiveConsole()
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
