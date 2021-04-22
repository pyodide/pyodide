"""
Source code analysis, transformation, compilation, execution.
"""

import ast
from asyncio import iscoroutine
from io import StringIO
from textwrap import dedent
import tokenize
from types import CodeType, coroutine
from typing import Any, Dict, List, Optional


def open_url(url: str) -> StringIO:
    """
    Fetches a given URL

    Parameters
    ----------
    url : str
       URL to fetch

    Returns
    -------
    io.StringIO
        the contents of the URL.
    """
    from js import XMLHttpRequest

    req = XMLHttpRequest.new()
    req.open("GET", url, False)
    req.send(None)
    return StringIO(req.response)


def _last_assign_to_expr(mod: ast.Module):
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


def _adjust_ast_to_store_result(target_name: str, mod: ast.Module) -> ast.Module:
    """Add instruction to store result of expression into a variable with
    name "target_name"
    """
    target = [ast.Name(target_name, ctx=ast.Store())]
    # We directly wrap Expr or Await node in an Assign node.
    last_node = mod.body[-1]
    if isinstance(last_node, (ast.Expr, ast.Await)):
        mod.body.pop()
        assign_rvalue = last_node.value
    else:
        # Remaining ast Nodes have no return value
        # (not sure what other possibilities there are actually...)
        assign_rvalue = ast.Constant(None, None)
    mod.body.append(ast.Assign(target, assign_rvalue))
    return mod


def parse_and_compile(
    source: str,
    filename="<exec>",
    return_mode: str = "last_expr",
    return_target: str = "_",
    flags: int = 0x0,
) -> CodeType:
    """

    Returns:
    --------
    code object
        first part's code object (or None)
    """
    # handle mis-indented input from multi-line strings
    source = dedent(source)

    mod = ast.parse(source, filename=filename)
    if not mod.body:
        return None

    if return_mode == "last_expr_or_assign":
        # If the last statement is a named assignment, add an extra
        # expression to the end with just the L-value so that we can
        # handle it with the last_expr code.
        _last_assign_to_expr(mod)

    # we extract last expression
    if return_mode.startswith(
        "last_expr"
    ) and isinstance(  # last_expr or last_expr_or_assign
        mod.body[-1], (ast.Expr, ast.Await)
    ):
        _adjust_ast_to_store_result(return_target, mod)

    # Update the line numbers shown in error messages.
    ast.fix_missing_locations(mod)
    # we compile
    mod = compile(mod, filename, "exec", flags=flags)  # type: ignore
    return mod


def should_quiet(source: str) -> bool:
    """
    Should we suppress output?

    Returns ``True`` if the last nonwhitespace character of ``source`` is a
    semicolon.

    Examples
    --------
    >>> CodeRunner().quiet('1 + 1') False CodeRunner().quiet('1 + 1 ;') True
    CodeRunner().quiet('1 + 1 # comment ;') False
    CodeRunner(quiet_trailing_semicolon=False).quiet('1 + 1 ;') False
    """
    # We need to wrap tokens in a buffer because:
    # "Tokenize requires one argument, readline, which must be
    # a callable object which provides the same interface as the
    # io.IOBase.readline() method of file objects"
    source_io = StringIO(source)
    tokens = list(tokenize.generate_tokens(source_io.readline))

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


RETURN_TARGET = "[[eval-code-result]]"


def _eval_code_common(
    source: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Dict[str, Any]] = None,
    return_mode: str = "last_expr",
    quiet_trailing_semicolon: bool = True,
    filename: str = "<exec>",
    flags: int = 0x0,
) -> Any:
    if quiet_trailing_semicolon and should_quiet(source):
        return_mode = "none"
    mod = parse_and_compile(
        source,
        return_target=RETURN_TARGET,
        return_mode=return_mode,
        flags=flags,
        filename=filename,
    )

    if mod:
        return eval(mod, globals, locals)


def eval_code(
    source: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Dict[str, Any]] = None,
    return_mode: str = "last_expr",
    return_target: str = "_",
    quiet_trailing_semicolon: bool = True,
    filename: str = "<exec>",
    flags: int = 0x0,
):
    """Runs a code string.

    Parameters
    ----------
    source
        the Python code to run.

    Returns
    -------
    If the last nonwhitespace character of ``source`` is a semicolon,
    return ``None``.
    If the last statement is an expression, return the
    result of the expression.
    Use the ``return_mode`` and ``quiet_trailing_semicolon`` parameters in the
    constructor to modify this default behavior.
    """
    if globals is None:
        globals = {}
    _eval_code_common(
        source,
        globals=globals,
        locals=locals,
        return_mode=return_mode,
        quiet_trailing_semicolon=quiet_trailing_semicolon,
        filename=filename,
        flags=flags,
    )
    if locals:
        return_dict = locals
    else:
        return_dict = globals
    if RETURN_TARGET in return_dict:
        return return_dict.pop(RETURN_TARGET)


async def eval_code_async(
    source: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Dict[str, Any]] = None,
    return_mode: str = "last_expr",
    quiet_trailing_semicolon: bool = True,
    filename: str = "<exec>",
    flags: int = 0x0,
) -> Any:
    """Runs a code string asynchronously.

    Uses
    [PyCF_ALLOW_TOP_LEVEL_AWAIT](https://docs.python.org/3/library/ast.html#ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    to compile the code.

    Parameters
    ----------
    source
        the Python source code to run.

    Returns
    -------
    If the last nonwhitespace character of ``source`` is a semicolon,
    return ``None``.
    If the last statement is an expression, return the
    result of the expression.
    Use the ``return_mode`` and ``quiet_trailing_semicolon`` parameters in the
    constructor to modify this default behavior.
    """
    flags = flags or ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    if globals is None:
        globals = {}
    coroutine = _eval_code_common(
        source,
        globals=globals,
        locals=locals,
        return_mode=return_mode,
        quiet_trailing_semicolon=quiet_trailing_semicolon,
        filename=filename,
        flags=flags,
    )
    if coroutine is False:
        return None
    if iscoroutine(coroutine):
        await coroutine
    if locals:
        return_dict = locals
    else:
        return_dict = globals
    if RETURN_TARGET in return_dict:
        return return_dict.pop(RETURN_TARGET)


class CodeRunner:
    """
    A helper class for eval_code and eval_code_async.

    Parameters
    ----------
    globals : ``dict``

        The global scope in which to execute code. This is used as the ``globals``
        parameter for ``exec``. See
        `the exec documentation <https://docs.python.org/3/library/functions.html#exec>`_
        for more info. If the ``globals`` is absent, it is set equal to a new empty
        dictionary.

    locals : ``dict``

        The local scope in which to execute code. This is used as the ``locals``
        parameter for ``exec``. As with ``exec``, if ``locals`` is absent, it is set equal
        to ``globals``. See
        `the exec documentation <https://docs.python.org/3/library/functions.html#exec>`_
        for more info.

    return_mode : ``str``

        Specifies what should be returned, must be one of ``'last_expr'``,
        ``'last_expr_or_assign'`` or ``'none'``. On other values an exception is
        raised.

        * ``'last_expr'`` -- return the last expression
        * ``'last_expr_or_assign'`` -- return the last expression or the last assignment.
        * ``'none'`` -- always return ``None``.

    quiet_trailing_semicolon : bool

        Whether a trailing semicolon should 'quiet' the
        result or not. Setting this to ``True`` (default) mimic the CPython's
        interpreter behavior ; whereas setting it to ``False`` mimic the IPython's
        interpreter behavior.

    filename : str

        The file name to use in error messages and stack traces

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
        self.flags = 0

    def run(self, source: str) -> Any:
        """Runs a code string.

        Parameters
        ----------
        code
           the Python code to run.

        Returns
        -------
        If the last nonwhitespace character of ``code`` is a semicolon,
        return ``None``.
        If the last statement is an expression, return the
        result of the expression.
        Use the ``return_mode`` and ``quiet_trailing_semicolon`` parameters in the
        constructor to modify this default behavior.
        """
        return eval_code(
            source,
            self.globals,
            self.locals,
            self.return_mode,
            self.quiet_trailing_semicolon,
            self.filename,
            self.flags,
        )

    async def run_async(self, source: str) -> Any:
        """Runs a code string asynchronously.

        Uses
        [PyCF_ALLOW_TOP_LEVEL_AWAIT](https://docs.python.org/3/library/ast.html#ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        to compile the code.

        Parameters
        ----------
        source
           the Python source code to run.

        Returns
        -------
        If the last nonwhitespace character of ``source`` is a semicolon,
        return ``None``.
        If the last statement is an expression, return the
        result of the expression.
        Use the ``return_mode`` and ``quiet_trailing_semicolon`` parameters in the
        constructor to modify this default behavior.
        """
        return await eval_code_async(
            source,
            self.globals,
            self.locals,
            self.return_mode,
            self.quiet_trailing_semicolon,
            self.filename,
            self.flags,
        )


def find_imports(source: str) -> List[str]:
    """
    Finds the imports in a string of code

    Parameters
    ----------
    code : str
       the Python code to run.

    Returns
    -------
    ``List[str]``
        A list of module names that are imported in the code.

    Examples
    --------
    >>> from pyodide import find_imports
    >>> code = "import numpy as np; import scipy.stats"
    >>> find_imports(code)
    ['numpy', 'scipy']
    """
    # handle mis-indented input from multi-line strings
    source = dedent(source)

    mod = ast.parse(source)
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
