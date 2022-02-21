import _pyodide.console
from _pyodide.console import Console, ConsoleFuture, repr_shorten

BANNER = _pyodide.console.BANNER
from _pyodide._base import CodeRunner

__all__ = ["Console", "PyodideConsole", "Banner", "repr_shorten", "ConsoleFuture"]


class PyodideConsole(Console):
    """A subclass of :any:`Console` that uses :any:`pyodide.loadPackagesFromImports` before running the code."""

    async def runcode(self, source: str, code: CodeRunner) -> ConsoleFuture:
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
