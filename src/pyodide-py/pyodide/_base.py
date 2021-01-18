"""
A library of helper utilities for connecting Python to the browser environment.
"""
# Added by C:
# JsException (from jsproxy.c)

import ast
from asyncio import iscoroutine
from io import StringIO
from textwrap import dedent
from typing import Dict, List, Any, Tuple, Optional
import tokenize


def open_url(url: str) -> StringIO:
    """
    Fetches a given URL

    Parameters
    ----------
    url
       URL to fetch

    Returns
    -------
    a io.StringIO object with the contents of the URL.
    """
    from js import XMLHttpRequest

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send(None)
    return StringIO(req.response)


class CodeRunner:
    """
    A code runner to serve eval_code and eval_code_async.

    Parameters
    ----------
    globals
        The global scope in which to execute code. This is used as the `exec`
        `globals` parameter. See
        [the exec documentation](https://docs.python.org/3/library/functions.html#exec)
        for more info.
    locals
        The local scope in which to execute code. This is used as the `exec`
        `locals` parameter. As with `exec`, if `locals` is absent, it is set equal
        to `globals`. See
        [the exec documentation](https://docs.python.org/3/library/functions.html#exec)
        for more info.
    return_mode
        Specifies what should be returned, must be one of 'last_expr',
        'last_expr_or_assign' or `None`. On other values an exception is raised.

        'last_expr' -- return the last expression
        'last_expr_or_assign' -- return the last expression or the last
        (named) assignment.
        'none' -- always return `None`.
    quiet_trailing_semicolon
        wether a trailing semicolon should 'quiet' the result or not.
        Setting this to `True` (default) mimic the CPython's interpret
        behavior ; whereas setting it to `False` mimic the IPython's
        interpret behavior.
    filename:
        file from which the code was read.

    Examples
    --------
    >>> CodeRunner().run("1+1")
    2
    >>> CodeRunner().run("1+1;")
    >>> runner = CodeRunner()
    >>> runner.run("x = 5")
    >>> runner.run("x + 1")
    6
    """

    def __init__(
        self,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        return_mode: str = "last_expr",
        quiet_trailing_semicolon: bool = True,
        filename: str = "<exec>",
    ):
        self.globals = globals if globals is not None else {}
        self.locals = locals if locals is not None else self.globals
        self.quiet_trailing_semicolon = quiet_trailing_semicolon
        self.filename = filename
        if return_mode not in ["last_expr", "last_expr_or_assign", "none", None]:
            raise ValueError(f"Unrecognized return_mode {return_mode!r}")
        self.return_mode = return_mode

    def quiet(self, code: str) -> bool:
        """
        If `quiet_trailing_semicolon` is set tot True in the constructor,
        does the last nonwhitespace character of code is a semicolon?

        Examples
        --------
        >>> CodeRunner().quiet('1 + 1')
        False
        >>> CodeRunner().quiet('1 + 1 ;')
        True
        >>> CodeRunner().quiet('1 + 1 # comment ;')
        False
        >>> CodeRunner(quiet_trailing_semicolon=False).quiet('1 + 1 ;')
        False
        """
        # largely inspired from IPython:
        # https://github.com/ipython/ipython/blob/86d24741188b0cedd78ab080d498e775ed0e5272/IPython/core/displayhook.py#L84

        if not self.quiet_trailing_semicolon:
            return False

        # We need to wrap tokens in a buffer because:
        # "Tokenize requires one argument, readline, which must be
        # a callable object which provides the same interface as the
        # io.IOBase.readline() method of file objects"
        codeio = StringIO(code)
        tokens = list(tokenize.generate_tokens(codeio.readline))

        for token in reversed(tokens):
            if token.type in (
                tokenize.ENDMARKER,
                tokenize.NL,  # ignoring empty lines (\n\n)
                tokenize.NEWLINE,
                tokenize.COMMENT,
            ):
                continue
            return (token.type == tokenize.OP) and (token.string == ";")

        return False

    def _last_assign_to_expr(self, mod: ast.Module):
        """
        Implementation of 'last_expr_or_assign' return_mode.
        It modify the supplyied AST module so that the last
        statement's value can be returned in 'last_expr' return_mode.
        """
        # Largely inspired from IPython:
        # https://github.com/ipython/ipython/blob/3587f5bb6c8570e7bbb06cf5f7e3bc9b9467355a/IPython/core/interactiveshell.py#L3229

        last_node = mod.body[-1]

        if isinstance(last_node, ast.Assign):
            # In this case there can be multiple targets as in `a = b = 1`.
            # We just take the first one.
            target = last_node.targets[0]
        elif isinstance(last_node, (ast.AugAssign, ast.AnnAssign)):
            target = last_node.target
        else:
            return
        if isinstance(target, ast.Name):
            last_node = ast.Expr(ast.Name(target.id, ast.Load()))
            mod.body.append(last_node)
            # Update the line numbers shown in error messages.
            ast.fix_missing_locations(mod)

    def _split_and_compile(self, code: str, flags: int = 0x0) -> Tuple[Any, Any]:
        """
        Split code in two parts, everything but last expression and
        last expresion then compile each part.

        Returns:
        --------
        code object
            first part's code object (or None)
        code object
            last expression's code object (or None)
        """
        # handle mis-indented input from multi-line strings
        code = dedent(code)

        mod = ast.parse(code)
        if not mod.body:
            return None, None

        if self.return_mode == "last_expr_or_assign":
            # If the last statement is a named assignment, add an extra
            # expression to the end with just the L-value so that we can
            # handle it with the last_expr code.
            self._last_assign_to_expr(mod)

        # we extract last expression
        if (
            self.return_mode.startswith("last_expr")  # last_expr or last_expr_or_assign
            and isinstance(mod.body[-1], (ast.Expr, ast.Await))
            and not self.quiet(code)
        ):
            last_expr = ast.Expression(mod.body.pop().value)  # type: ignore
        else:
            last_expr = None  # type: ignore

        # we compile
        mod = compile(mod, self.filename, "exec", flags=flags)  # type: ignore
        if last_expr is not None:
            last_expr = compile(last_expr, self.filename, "eval", flags=flags)  # type: ignore

        return mod, last_expr

    def run(self, code: str) -> Any:
        """Runs a code string.

        Parameters
        ----------
        code
           the Python code to run.

        Returns
        -------
        If the last nonwhitespace character of code is a semicolon,
        return `None`.
        If the last statement is an expression, return the
        result of the expression.
        Use the `return_mode` and `quiet_trailing_semicolon` parameters in the
        constructor to modify this default behavior.
        """
        mod, last_expr = self._split_and_compile(code)

        # running first part
        if mod is not None:
            exec(mod, self.globals, self.locals)

        # evaluating last expression
        if last_expr is not None:
            return eval(last_expr, self.globals, self.locals)

    async def run_async(self, code: str) -> Any:
        """ //!\\ WARNING //!\\
        This is not working yet. For use once we add an EventLoop.

        Note: see `_eval_code_async`.
        """
        mod, last_expr = self._split_and_compile(
            code, flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT  # type: ignore
        )
        # running first part
        if mod is not None:
            coro = eval(mod, self.globals, self.locals)
            if iscoroutine(coro):
                await coro

        # evaluating last expression
        if last_expr is not None:
            res = eval(last_expr, self.globals, self.locals)
            if iscoroutine(res):
                res = await res
            return res


def eval_code(
    code: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Dict[str, Any]] = None,
    return_mode: str = "last_expr",
    quiet_trailing_semicolon: bool = True,
    filename: str = "<exec>",
) -> Any:
    """Runs a code string.

    Parameters
    ----------
    code
       the Python code to run.
    globals
        The global scope in which to execute code. This is used as the `exec`
        `globals` parameter. See
        [the exec documentation](https://docs.python.org/3/library/functions.html#exec)
        for more info.
    locals
        The local scope in which to execute code. This is used as the `exec`
        `locals` parameter. As with `exec`, if `locals` is absent, it is set equal
        to `globals`. See
        [the exec documentation](https://docs.python.org/3/library/functions.html#exec)
        for more info.
    return_mode
        Specifies what should be returned, must be one of 'last_expr',
        'last_expr_or_assign' or `None`. On other values an exception is raised.

        'last_expr' -- return the last expression
        'last_expr_or_assign' -- return the last expression or the last
        (named) assignment.
        'none' -- always return `None`.
    quiet_trailing_semicolon
        whether a trailing semicolon should 'quiet' the result or not.
        Setting this to `True` (default) mimic the CPython's interpret
        behavior ; whereas setting it to `False` mimic the IPython's
    filename:
       file from which the code was read.

    Returns
    -------
    If the last nonwhitespace character of code is a semicolon return `None`.
    If the last statement is an expression, return the
    result of the expression.
    Use the `return_mode` and `quiet_trailing_semicolon` parameters to modify
    this default behavior.
    """
    return CodeRunner(
        globals=globals,
        locals=locals,
        return_mode=return_mode,
        quiet_trailing_semicolon=quiet_trailing_semicolon,
        filename=filename,
    ).run(code)


async def eval_code_async(
    code: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Dict[str, Any]] = None,
    return_mode: str = "last_expr",
    quiet_trailing_semicolon: bool = True,
    filename: str = "<exec>",
) -> Any:
    """ //!\\ WARNING //!\\
    This is not working yet. For use once we add an EventLoop.

    Note: once async is working, one should:
      - rename `_eval_code_async` in `eval_code_async` (remove leading '_')
      - remove exceptions here and in `CodeRunner.run_async`
      - add docstrings here and in `CodeRunner.run_async`
      - add tests
    """
    return await CodeRunner(
        globals=globals,
        locals=locals,
        return_mode=return_mode,
        quiet_trailing_semicolon=quiet_trailing_semicolon,
        filename=filename,
    ).run_async(code)


def find_imports(code: str) -> List[str]:
    """
    Finds the imports in a string of code

    Parameters
    ----------
    code
       the Python code to run.

    Returns
    -------
    A list of module names that are imported in the code.

    Examples
    --------
    >>> from pyodide import find_imports
    >>> code = "import numpy as np; import scipy.stats"
    >>> find_imports(code)
    ['numpy', 'scipy']
    """
    # handle mis-indented input from multi-line strings
    code = dedent(code)

    mod = ast.parse(code)
    imports = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            for name in node.names:
                node_name = name.name
                imports.add(node_name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module
            if module_name is None:
                continue
            imports.add(module_name.split(".")[0])
    return list(sorted(imports))


def as_nested_list(obj) -> List:
    """Convert a nested JS array to nested Python list.

    Assumes a Javascript object is made of (possibly nested) arrays and
    converts them to nested Python lists.

    Parameters
    ----------
    obj
       a Javscript object made of nested arrays.

    Returns
    -------
    Python list, or a nested Python list
    """
    try:
        it = iter(obj)
        return [as_nested_list(x) for x in it]
    except TypeError:
        return obj
