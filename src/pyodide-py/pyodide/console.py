from typing import Optional, Callable, Any, List, Tuple
import code
import io
import sys
import platform
from contextlib import contextmanager
import builtins
import rlcompleter

# this import can fail when we are outside a browser (e.g. for tests)
try:
    import js
    import pyodide_js

    _dummy_promise = js.Promise.resolve()
    _load_packages_from_imports = pyodide_js.loadPackagesFromImports

except ImportError:

    class _FakePromise:
        """A promise that mimic the JS promises.

        Only `then is supported` and there is no asynchronicity.
        execution occurs when then is call.

        This is mainly to fake `load_packages_from_imports`
        and `InteractiveConsole.run_complete` in contexts
        where JS promises are not available (tests)."""

        def __init__(self, args=None):
            self.args = (args,) if args is not None else ()

        def then(self, func, *args):
            return _FakePromise(func(*self.args))

    _dummy_promise = _FakePromise()

    def _load_packages_from_imports(*args):
        return _dummy_promise


__all__ = ["InteractiveConsole", "repr_shorten", "displayhook"]


class _StdStream(io.TextIOWrapper):
    """
    Custom std stream to retdirect sys.stdout/stderr in InteractiveConsole.

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


class InteractiveConsole(code.InteractiveConsole):
    """Interactive Pyodide console

    Base implementation for an interactive console that manages
    stdout/stderr redirection. Since packages are loaded before running
    code, `runcode` returns a JS promise. Override `sys.displayhook` to
    catch the result of an execution.

    `self.stdout_callback` and `self.stderr_callback` can be overloaded.

    Parameters
    ----------
    locals
        Namespace to evaluate code.
    stdout_callback
        Function to call at each `sys.stdout` flush.
    stderr_callback
        Function to call at each `sys.stderr` flush.
    persistent_stream_redirection
        Wether or not the std redirection should be kept between calls to
        `runcode`.
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
        self.run_complete = _dummy_promise
        self._completer = rlcompleter.Completer(self.locals)  # type: ignore
        # all nonalphanums except '.'
        # see https://github.com/python/cpython/blob/a4258e8cd776ba655cc54ba54eaeffeddb0a267c/Modules/readline.c#L1211
        self.completer_word_break_characters = (
            """ \t\n`~!@#$%^&*()-=+[{]}\\|;:'\",<>/?"""
        )

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

        Syntax errors are not thrown by runcode but here in runsource.
        This is why we force redirection here since doing twice
        is not an issue."""

        with self.stdstreams_redirections():
            return super().runsource(*args, **kwargs)

    def runcode(self, code):
        """Load imported packages then run code, async.

        To achieve nice result representation, the interactive console
        is fully implemented in Python. This has a major drawback:
        packages should be loaded from here. This is why this
        function sets the promise `self.run_complete`.
        If you need to wait for the end of the computation,
        you should await for it."""
        parent_runcode = super().runcode
        source = "\n".join(self.buffer)

        def load_packages_and_run(*args):
            def run(*args):
                with self.stdstreams_redirections():
                    parent_runcode(code)
                    # in CPython's REPL, flush is performed
                    # by input(prompt) at each new prompt ;
                    # since we are not using input, we force
                    # flushing here
                    self.flush_all()

            return _load_packages_from_imports(source).then(run)

        self.run_complete = self.run_complete.then(load_packages_and_run)

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

        You can use `completer_word_break_characters` to get/set the
        way `source` is splitted to find the last part to be completed.

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


def repr_shorten(
    value: Any, limit: int = 1000, split: Optional[int] = None, separator: str = "..."
):
    """Compute the string representation of `value` and shorten it
    if necessary.

    If it is longer than `limit` then return the firsts `split`
    characters and the last `split` characters seperated by '...'.
    Default value for `split` is `limit // 2`.
    """
    if split is None:
        split = limit // 2
    text = repr(value)
    if len(text) > limit:
        text = f"{text[:split]}{separator}{text[-split:]}"
    return text


def displayhook(value, repr: Callable[[Any], str]):
    """A displayhook with custom `repr` function.

    It is intendend to overload `sys.displayhook`. Note that monkeypatch
    `builtins.repr` does not work in `sys.displayhook`. The pointer to
    `repr` seems hardcoded in default `sys.displayhook` version
    (which is written in C)."""
    # from https://docs.python.org/3/library/sys.html#sys.displayhook
    # If value is not None, this function prints repr(value) to
    # sys.stdout, and saves value in builtins._. If repr(value) is not
    # encodable to sys.stdout.encoding with sys.stdout.errors error
    # handler (which is probably 'strict'), encode it to
    # sys.stdout.encoding with 'backslashreplace' error handler.
    if value is None:
        return
    builtins._ = None  # type: ignore
    text = repr(value)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        bytes = text.encode(sys.stdout.encoding, "backslashreplace")
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(bytes)
        else:
            text = bytes.decode(sys.stdout.encoding, "strict")
            sys.stdout.write(text)
    sys.stdout.write("\n")
    builtins._ = value  # type: ignore
