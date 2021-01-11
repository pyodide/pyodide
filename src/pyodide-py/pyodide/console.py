from typing import Optional, Callable
import code
import io
import sys


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
    stdout/stderr. Their value will be restored at destruction or
    at `restore_stdstreams` call.

    `self.stdout_callback` and `self.stderr_callback` can be overloaded.

    Parameters
    ----------
    stdout_callback
        Function to call at each `sys.stdout` flush.
    stderr_callback
        Function to call at each `sys.stderr` flush.
    """

    def __init__(
        self,
        locals: Optional[dict] = None,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(locals)
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self.redirect_stdstreams()

    def redirect_stdstreams(self):
        """ Toggle stdout/stderr redirections. """

        # we use meta callbacks to allow self.std{out,err}_callback
        # overloading.
        # we check callback against None at each call since it can be
        # changed dynamically.

        def meta_stdout_callback(*args):
            if self.stdout_callback is not None:
                return self.stdout_callback(*args)

        def meta_stderr_callback(*args):
            if self.stderr_callback is not None:
                return self.stderr_callback(*args)

        # for later restore
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr

        # it would be more robust to use sys.stdout.name and sys.stderr.name
        # but testing system oveload them. Anyway it should be pretty stable
        # upstream.
        sys.stdout = _StdStream(meta_stdout_callback, name="<stdout>")
        sys.stderr = _StdStream(meta_stderr_callback, name="<stderr>")

    def restore_stdstreams(self):
        """Restore stdout/stderr to the value it was before
        the creation of the object."""
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr

    def __del__(self):
        self.restore_stdstreams()
