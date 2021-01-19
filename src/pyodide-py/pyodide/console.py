from typing import Optional, Callable
import code
import io
import sys
import platform

__all__ = ["InteractiveConsole"]


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
    stdout/stderr redirection.

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
        self._persistent_stream_redirection = persistent_stream_redirection
        if self._persistent_stream_redirection:
            self.redirect_stdstreams()

    def redirect_stdstreams(self):
        """ Toggle stdout/stderr redirections. """

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

    def restore_stdstreams(self):
        """Restore stdout/stderr to the value it was before
        the creation of the object."""
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr

    def runcode(self, code):
        if self._persistent_stream_redirection:
            super().runcode(code)
        else:
            self.redirect_stdstreams()
            super().runcode(code)
            self.restore_stdstreams()

    def __del__(self):
        if self._persistent_stream_redirection:
            self.restore_stdstreams()

    def banner(self):
        """ A banner similar to the one printed by the real Python interpreter. """
        # copyied from https://github.com/python/cpython/blob/799f8489d418b7f9207d333eac38214931bd7dcc/Lib/code.py#L214
        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        return f"Python {platform.python_version()} {platform.python_build()} on WebAssembly VM\n{cprt}"
