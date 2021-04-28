import traceback
from typing import Optional, Callable, Any, List, Tuple
import code
import io
import sys
import platform
from contextlib import contextmanager
import rlcompleter
import asyncio
from pyodide import eval_code_async
import ast

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


__all__ = ["repr_shorten"]


class _StdStream(io.TextIOWrapper):
    """
    Custom std stream to retdirect sys.stdout/stderr in _InteractiveConsole.

    Parmeters
    ---------
    flush_callback
        Function to call at each flush.
    """

    def __init__(
        self, flush_callback: Callable[[str], None], name: Optional[str] = None
    ):
        # we just need to set internal buffer's name as
        # it will automatically buble up to each buffer
        internal_buffer = _CallbackBuffer(flush_callback, name=name)
        buffer = io.BufferedWriter(internal_buffer)
        super().__init__(buffer, line_buffering=True)  # type: ignore


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
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        persistent_stream_redirection: bool = False,
    ):
        super().__init__(locals)
        self._stdout = None
        self._stderr = None
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self._streams_redirected = False
        if persistent_stream_redirection:
            self.redirect_stdstreams()
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

    def redirect_stdstreams(self):
        """ Toggle stdout/stderr redirections. """
        # already redirected?
        if self._streams_redirected:
            return

        if self._stdout is None:
            # we use meta callbacks to allow self.std{out,err}_callback
            # overloading.
            # we check callback against None at each call since it can be
            # changed dynamically.
            def meta_stdout_callback(*args):
                if self.stdout_callback is not None:
                    return self.stdout_callback(*args)

            # for later restore
            self._old_stdout = sys.stdout

            # it would be more robust to use sys.stdout.name but testing
            # system oveload them. Anyway it should be pretty stable
            # upstream.
            self._stdout = _StdStream(meta_stdout_callback, name="<stdout>")

        if self._stderr is None:

            def meta_stderr_callback(*args):
                if self.stderr_callback is not None:
                    return self.stderr_callback(*args)

            self._old_stderr = sys.stderr
            self._stderr = _StdStream(meta_stderr_callback, name="<stderr>")

        # actual redirection
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        self._streams_redirected = True

    def restore_stdstreams(self):
        """Restore stdout/stderr to the value it was before
        the creation of the object."""
        if self._streams_redirected:
            sys.stdout = self._old_stdout
            sys.stderr = self._old_stderr
            self._streams_redirected = False

    @contextmanager
    def stdstreams_redirections(self):
        """Ensure std stream redirection.

        This supports nesting."""
        if self._streams_redirected:
            yield
        else:
            self.redirect_stdstreams()
            yield
            self.restore_stdstreams()

    def flush_all(self):
        """ Force stdout/stderr flush. """
        with self.stdstreams_redirections():
            sys.stdout.flush()
            sys.stderr.flush()

    def runsource(self, *args, **kwargs):
        """Force streams redirection.

        Syntax errors are not thrown by :any:`_InteractiveConsole.runcode` but
        here in :any:`_InteractiveConsole.runsource`. This is why we force
        redirection here since doing twice is not an issue.
        """

        with self.stdstreams_redirections():
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
        with self.stdstreams_redirections():
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

    def __del__(self):
        self.restore_stdstreams()

    def banner(self):
        """ A banner similar to the one printed by the real Python interpreter. """
        # copyied from https://github.com/python/cpython/blob/799f8489d418b7f9207d333eac38214931bd7dcc/Lib/code.py#L214
        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        version = platform.python_version()
        build = f"({', '.join(platform.python_build())})"
        return f"Python {version} {build} on WebAssembly VM\n{cprt}"

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
