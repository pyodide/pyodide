from typing import Optional
import code
import io
import sys


class InteractiveConsole(code.InteractiveConsole):
    """
    Base implementation for an interactive console that manages
    stdout/stderr. It does not actually run any code.

    A subclass may overload runcode and access std streams via
    sys.stdout.getvalue() and sys.stderr.getvalue(). Remember to
    start calling parent's runcode.
    """

    def __init__(self, locals: Optional[dict] = None):
        super().__init__(locals)

    def runcode(self, code):
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
